import ast
import pathlib
import shutil
from collections import defaultdict
from dataclasses import dataclass

MODEL_EMBED = "nomic-embed-text"
VECTOR_DB_PATH = "vector_db"
GRAPH_DB_PATH = "graph_db"
SKIP_DIRS = {"venv", ".venv", "env", "__pycache__", ".git", "node_modules", "site-packages"}

FUNC_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)


@dataclass
class ParsedFile:
    module: str          # เช่น "app.utils"
    path: pathlib.Path
    source: str
    tree: ast.AST


@dataclass
class FuncInfo:
    full: str            # "app.utils::Helper.run"  (คีย์ไม่ซ้ำกัน)
    qualname: str        # "Helper.run"
    short: str           # "run"
    module: str
    pf: ParsedFile
    node: ast.AST


# ---------- helpers ----------
def load_files(root: pathlib.Path) -> list[ParsedFile]:
    files = []
    for py_file in sorted(root.rglob("*.py")):
        rel = py_file.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except Exception as e:
            print(f"ข้ามไฟล์ {py_file}: {e}")
            continue
        parts = list(rel.with_suffix("").parts)
        if parts[-1] == "__init__" and len(parts) > 1:
            parts = parts[:-1]
        files.append(ParsedFile(".".join(parts), py_file, source, tree))
    return files


def iter_functions(node, prefix=""):
    """เดินหา function/method พร้อมชื่อเต็ม เช่น Class.method (กันชื่อซ้ำ เช่น __init__)"""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, FUNC_TYPES):
            qual = f"{prefix}{child.name}"
            yield qual, child
            yield from iter_functions(child, qual + ".")
        elif isinstance(child, ast.ClassDef):
            yield from iter_functions(child, f"{prefix}{child.name}.")
        else:
            yield from iter_functions(child, prefix)


def iter_calls(func_node):
    """หา Call ในฟังก์ชัน โดยไม่ลงไปนับฟังก์ชันซ้อนใน (มันมีโหนดของตัวเองแล้ว)"""
    stack = list(ast.iter_child_nodes(func_node))
    while stack:
        n = stack.pop()
        if isinstance(n, FUNC_TYPES + (ast.ClassDef,)):
            continue
        if isinstance(n, ast.Call):
            yield n
        stack.extend(ast.iter_child_nodes(n))


def call_name(call: ast.Call):
    f = call.func
    if isinstance(f, ast.Name):        # foo()
        return f.id
    if isinstance(f, ast.Attribute):   # self.foo() / obj.foo()
        return f.attr
    return None


def collect_functions(files: list[ParsedFile]) -> dict[str, FuncInfo]:
    funcs: dict[str, FuncInfo] = {}
    for pf in files:
        for qual, node in iter_functions(pf.tree):
            full = f"{pf.module}::{qual}"
            funcs.setdefault(full, FuncInfo(full, qual, node.name, pf.module, pf, node))
    return funcs


# ---------- Vector DB ----------
def build_vector_db(funcs: dict[str, FuncInfo]):
    from langchain_community.vectorstores import FAISS
    from langchain_ollama import OllamaEmbeddings
    from langchain_core.documents import Document

    docs = []
    for f in funcs.values():
        lines = f.pf.source.split("\n")[f.node.lineno - 1: f.node.end_lineno]
        docs.append(Document(
            page_content="\n".join(lines),
            metadata={"function": f.qualname, "module": f.module,
                      "file": str(f.pf.path), "line": f.node.lineno},
        ))

    vp = pathlib.Path(VECTOR_DB_PATH)
    if not docs:
        print("⚠️ ไม่พบฟังก์ชันเลย ข้ามการสร้าง Vector DB")
        if vp.exists():
            shutil.rmtree(vp)  # กัน index เก่าค้าง
        return

    print(f"เจอ {len(docs)} ฟังก์ชัน กำลังสร้าง Vector DB...")
    vs = FAISS.from_documents(docs, OllamaEmbeddings(model=MODEL_EMBED))
    vs.save_local(VECTOR_DB_PATH)
    print("✅ สร้าง Vector DB (FAISS) สำเร็จ!")


# ---------- Graph DB ----------
def _remove_old_graph():
    for p in (pathlib.Path(GRAPH_DB_PATH), pathlib.Path(GRAPH_DB_PATH + ".wal")):
        if p.exists():
            shutil.rmtree(p) if p.is_dir() else p.unlink()


def build_graph_db(files: list[ParsedFile], funcs: dict[str, FuncInfo]):
    import kuzu

    print("กำลังสร้าง Graph DB...")
    _remove_old_graph()
    db = kuzu.Database(GRAPH_DB_PATH)
    conn = kuzu.Connection(db)
    conn.execute("CREATE NODE TABLE Function (name STRING, qualname STRING, file STRING, line INT64, PRIMARY KEY (name))")
    conn.execute("CREATE NODE TABLE Module (name STRING, filepath STRING, PRIMARY KEY (name))")
    conn.execute("CREATE REL TABLE CALLS (FROM Function TO Function)")
    conn.execute("CREATE REL TABLE DEFINED_IN (FROM Function TO Module)")
    conn.execute("CREATE REL TABLE IMPORTS (FROM Module TO Module)")

    # โหนด
    for pf in files:
        conn.execute("CREATE (:Module {name: $n, filepath: $p})", {"n": pf.module, "p": str(pf.path)})
    for f in funcs.values():
        conn.execute(
            "CREATE (:Function {name: $n, qualname: $q, file: $f, line: $l})",
            {"n": f.full, "q": f.qualname, "f": str(f.pf.path), "l": f.node.lineno},
        )
        conn.execute(
            "MATCH (a:Function {name: $a}), (m:Module {name: $m}) CREATE (a)-[:DEFINED_IN]->(m)",
            {"a": f.full, "m": f.module},
        )

    # CALLS: ชื่อที่ถูกเรียก -> ฟังก์ชันจริงในโปรเจกต์ (ถ้าเจอในไฟล์เดียวกันให้เลือกอันนั้นก่อน)
    by_short = defaultdict(list)
    for f in funcs.values():
        by_short[f.short].append(f.full)

    calls = set()
    for f in funcs.values():
        for call in iter_calls(f.node):
            name = call_name(call)
            candidates = by_short.get(name, [])
            same_module = [c for c in candidates if funcs[c].module == f.module]
            for target in (same_module or candidates):
                calls.add((f.full, target))
    for a, b in calls:
        conn.execute(
            "MATCH (a:Function {name: $a}), (b:Function {name: $b}) CREATE (a)-[:CALLS]->(b)",
            {"a": a, "b": b},
        )

    # IMPORTS: เฉพาะโมดูลที่อยู่ในโปรเจกต์ (absolute import เท่านั้น)
    modules = {pf.module for pf in files}
    imports = set()
    for pf in files:
        for node in ast.walk(pf.tree):
            cands = []
            if isinstance(node, ast.Import):
                cands = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                cands = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
            for c in cands:
                if c in modules and c != pf.module:
                    imports.add((pf.module, c))
    for a, b in imports:
        conn.execute(
            "MATCH (a:Module {name: $a}), (b:Module {name: $b}) CREATE (a)-[:IMPORTS]->(b)",
            {"a": a, "b": b},
        )

    print(f"✅ สร้าง Graph DB (Kuzu) สำเร็จ! {len(funcs)} functions, {len(calls)} calls, {len(imports)} imports")


def build_databases(source_directory: str):
    root = pathlib.Path(source_directory)
    print(f"กำลังสแกนโค้ดในโฟลเดอร์: {root}")
    files = load_files(root)
    funcs = collect_functions(files)
    build_vector_db(funcs)
    build_graph_db(files, funcs)


if __name__ == "__main__":
    build_databases("my_dataset")