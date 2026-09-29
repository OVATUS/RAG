from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
import kuzu

class QuestionRouter:
    # คำหลักเชิงโครงสร้าง สำหรับส่งไป Graph DB
    GRAPH_KEYWORDS = ["calls", "called by", "imports", "depends on", "impact", "affects", "who calls", "what calls"]

    def classify(self, question: str) -> str:
        q_lower = question.lower()
        if any(kw in q_lower for kw in self.GRAPH_KEYWORDS):
            return "graph"
        return "vector"

class HybridRAG:
    def __init__(self, vectorstore_path: str = "vector_db", graph_db_path: str = "graph_db"):
        self.embeddings = OllamaEmbeddings(model="nomic-embed-text")
        self.vectorstore = FAISS.load_local(vectorstore_path, self.embeddings, allow_dangerous_deserialization=True)
        self.db = kuzu.Database(graph_db_path)
        self.conn = kuzu.Connection(self.db)
        self.llm = ChatOllama(model="qwen2.5-coder:7b", temperature=0.0)
        self.router = QuestionRouter()

    def _vector_query(self, question: str) -> dict:
        docs = self.vectorstore.similarity_search(question, k=5)
        context = "\n\n".join([f"# {d.metadata['function']} in {d.metadata['file']}\n{d.page_content}" for d in docs])
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a coding assistant. Answer using ONLY this code context:\n\n{context}"),
            ("human", "{question}")
        ])
        answer = (prompt | self.llm).invoke({"context": context, "question": question})
        
        return {"answer": answer.content, "source": "vector", "docs": [d.metadata for d in docs]}

    def _graph_query(self, question: str) -> dict:
        # สมมติฐานง่ายๆ ดึงฟังก์ชันทั้งหมดมาให้ LLM วิเคราะห์โครงสร้าง
        result = self.conn.execute("MATCH (a:Function)-[:CALLS]->(b:Function) RETURN a.name AS caller, b.name AS callee LIMIT 50")
        df = result.get_as_df()
        context = f"Call Graph Relationships:\n{df.to_string()}"

        prompt = ChatPromptTemplate.from_messages([
            ("system", "Answer the code structure question using ONLY the provided graph data.\n\nGraph data:\n{context}"),
            ("human", "{question}")
        ])
        answer = (prompt | self.llm).invoke({"context": context, "question": question})
        return {"answer": answer.content, "source": "graph", "docs": []}

    def query(self, question: str) -> dict:
        route = self.router.classify(question)
        if route == "graph":
            return self._graph_query(question)
        return self._vector_query(question)