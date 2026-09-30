import re

import kuzu
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama, OllamaEmbeddings


URL_FRAG = re.compile(r"(?:^|\s)(/[\w\-]+(?:/[\w\-<>:]*)*)")


def _route_regex(route: str) -> str:
    """แปลง /bookings/<int:pk>/delete/ เป็น regex ที่จับ /bookings/1/delete/ ได้"""
    parts = re.split(r"(<[^>]+>)", route.rstrip("/"))
    return "".join("[^/]+" if p.startswith("<") else re.escape(p) for p in parts)


class QuestionRouter:
    # คำเชิงโครงสร้าง -> Graph DB (ใช้ word boundary กัน "recalls" ฯลฯ, มีคำไทยด้วย)
    GRAPH_REGEX = re.compile(
        r"\b(calls?|called by|callers?|callees?|imports?|imported by|depends? on|"
        r"dependenc(?:y|ies)|impact|affects?|urls?|routes?|endpoints?)\b|"
        r"เรียกใช้|ใครเรียก|ผลกระทบ|พึ่งพา|นำเข้า|เส้นทาง|ลิงก์",
        re.IGNORECASE,
    )

    def classify(self, question: str) -> str:
        if self.GRAPH_REGEX.search(question) or URL_FRAG.search(question):
            return "graph"
        return "vector"


class HybridRAG:
    def __init__(self, vectorstore_path: str = "vector_db", graph_db_path: str = "graph_db"):
        self.embeddings = OllamaEmbeddings(model="nomic-embed-text")
        self.vectorstore = FAISS.load_local(
            vectorstore_path, self.embeddings, allow_dangerous_deserialization=True
        )  # โอเคเพราะเป็น index ที่เราสร้างเอง
        self.db = kuzu.Database(graph_db_path, read_only=True)
        self.conn = kuzu.Connection(self.db)
        self.llm = ChatOllama(model="qwen2.5-coder:7b", temperature=0.0)
        self.router = QuestionRouter()

        # โหลดรายชื่อฟังก์ชัน/โมดูลไว้จับคู่กับคำถาม
        self.functions = [(n, q) for n, q in self._rows("MATCH (f:Function) RETURN f.name, f.qualname")]
        self.modules = [r[0] for r in self._rows("MATCH (m:Module) RETURN m.name")]
        self.routes = self._rows("MATCH (r:Route)-[:ROUTES_TO]->(f:Function) RETURN r.name, f.name")

    # ---------- helpers ----------
    def _rows(self, query: str, params: dict | None = None) -> list:
        result = self.conn.execute(query, params) if params else self.conn.execute(query)
        rows = []
        while result.has_next():
            rows.append(result.get_next())
        return rows

    def _find_targets(self, question: str):
        tokens = {t.rstrip(".") for t in re.findall(r"[A-Za-z_][\w.]*", question)}
        funcs = [n for n, q in self.functions
                 if q in tokens or q.split(".")[-1] in tokens
                 or (q.endswith(".__init__") and q[: -len(".__init__")] in tokens)][:10]
        mods = [m for m in self.modules if m in tokens or m.split(".")[-1] in tokens][:10]
        return funcs, mods

    def _match_routes(self, frag: str) -> list:
        path = frag.rstrip("/")
        hit = [(r, f) for r, f in self.routes if re.fullmatch(_route_regex(r), path)]
        return hit or [(r, f) for r, f in self.routes if path.strip("/") in r]

    def _graph_context(self, question: str) -> list[str] | None:
        """คืนรายการความสัมพันธ์ที่เกี่ยวกับสิ่งที่ถูกถามถึง หรือ None ถ้าจับชื่อไม่ได้เลย"""
        q = question.lower()
        funcs, mods = self._find_targets(question)

        url_frags = [m.strip() for m in URL_FRAG.findall(question)]
        if url_frags or (re.search(r"\burls?\b|\broutes?\b|endpoint|เส้นทาง|ลิงก์", q) and funcs):
            lines = []
            if funcs:
                rows = self._rows(
                    "MATCH (r:Route)-[:ROUTES_TO]->(f:Function) WHERE f.name IN $t "
                    "RETURN r.name, f.name LIMIT 50", {"t": funcs})
                lines += [f"URL {r} is handled by view {f}" for r, f in rows]
            for frag in url_frags[:3]:
                lines += [f"URL {r} is handled by view {f}" for r, f in self._match_routes(frag)]
            targets = funcs + url_frags
        elif mods and re.search(r"import|depend|นำเข้า|พึ่งพา", q):
            rows = self._rows(
                "MATCH (a:Module)-[:IMPORTS]->(b:Module) "
                "WHERE a.name IN $t OR b.name IN $t RETURN a.name, b.name LIMIT 100",
                {"t": mods},
            )
            lines = [f"{a} imports {b}" for a, b in rows]
            targets = mods
        elif funcs:
            if re.search(r"impact|affect|ผลกระทบ", q):
                rows = self._rows(
                    "MATCH (a:Function)-[:CALLS*1..3]->(b:Function) "
                    "WHERE b.name IN $t RETURN DISTINCT a.name, b.name LIMIT 100",
                    {"t": funcs},
                )
                lines = [f"{a} depends (directly or indirectly) on {b}" for a, b in rows]
            else:
                rows = self._rows(
                    "MATCH (a:Function)-[:CALLS]->(b:Function) "
                    "WHERE a.name IN $t OR b.name IN $t RETURN a.name, b.name LIMIT 100",
                    {"t": funcs},
                )
                lines = [f"{a} calls {b}" for a, b in rows]
            targets = funcs
        else:
            return None

        if not lines:
            lines = [f"No relationships found in the graph for: {', '.join(targets)}"]
        return lines

    def _answer(self, question: str, graph_lines: list[str] | None) -> dict:
        docs = self.vectorstore.similarity_search(question, k=3 if graph_lines else 5)
        code_ctx = "\n\n".join(
            f"# {d.metadata.get('kind', 'code')} {d.metadata['function']} in {d.metadata['file']}\n{d.page_content}"
            for d in docs
        )
        parts = []
        if graph_lines:
            parts.append("Graph relationships:\n" + "\n".join(graph_lines))
        parts.append("Code:\n" + code_ctx)
        context = "\n\n".join(parts)

        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are a coding assistant. Answer using ONLY the context below. "
             "If the context is not enough, say you cannot find it in the codebase. "
             "Reply in the same language as the question.\n\n{context}"),
            ("human", "{question}"),
        ])
        answer = (prompt | self.llm).invoke({"context": context, "question": question})
        return {
            "answer": answer.content,
            "source": "graph" if graph_lines else "vector",
            "docs": [d.metadata for d in docs],
            "graph_rows": graph_lines or [],
        }

    # ---------- public ----------
    def query(self, question: str) -> dict:
        graph_lines = None
        if self.router.classify(question) == "graph":
            graph_lines = self._graph_context(question)  # None = จับชื่อไม่ได้ -> fallback ไป vector
        return self._answer(question, graph_lines)