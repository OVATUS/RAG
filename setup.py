import os
import ast
import pathlib
import shutil
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document
import kuzu

MODEL_EMBED = "nomic-embed-text"
VECTOR_DB_PATH = "vector_db"
GRAPH_DB_PATH = "graph_db"

def build_databases(source_directory: str):
    print(f"กำลังสแกนโค้ดในโฟลเดอร์: {source_directory}")
    
    # 1. อ่านไฟล์และสร้าง Vector DB (FAISS)
    docs = []
    for py_file in pathlib.Path(source_directory).rglob("*.py"):
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    lines = source.split("\n")[node.lineno - 1: node.end_lineno]
                    docs.append(Document(
                        page_content="\n".join(lines),
                        metadata={"function": node.name, "file": str(py_file), "line": node.lineno}
                    ))
        except Exception as e:
            print(f"ข้ามไฟล์ {py_file}: {e}")
            continue

    if docs:
        print(f"เจอ {len(docs)} ฟังก์ชัน กำลังสร้าง Vector DB...")
        embeddings = OllamaEmbeddings(model=MODEL_EMBED)
        vs = FAISS.from_documents(docs, embeddings)
        vs.save_local(VECTOR_DB_PATH)
        print("✅ สร้าง Vector DB (FAISS) สำเร็จ!")

    # 2. สร้าง Graph DB (Kuzu)
    print("กำลังสร้าง Graph DB...")
    db_path = pathlib.Path(GRAPH_DB_PATH)
    
    # เช็กว่าเป็นไฟล์หรือโฟลเดอร์ก่อนลบ ป้องกัน Error
    if db_path.exists():
        if db_path.is_dir():
            shutil.rmtree(db_path)
        else:
            db_path.unlink()
    
    db = kuzu.Database(GRAPH_DB_PATH)
    conn = kuzu.Connection(db)
    conn.execute("CREATE NODE TABLE IF NOT EXISTS Function (name STRING, file STRING, line INT64, PRIMARY KEY (name))")
    conn.execute("CREATE NODE TABLE IF NOT EXISTS Module (name STRING, filepath STRING, PRIMARY KEY (name))")
    conn.execute("CREATE REL TABLE IF NOT EXISTS CALLS (FROM Function TO Function)")
    conn.execute("CREATE REL TABLE IF NOT EXISTS DEFINED_IN (FROM Function TO Module)")

    for py_file in pathlib.Path(source_directory).rglob("*.py"):
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
            module_name = str(py_file).replace("\\", "/").replace(".py", "")
            conn.execute("MERGE (:Module {name: $n, filepath: $fp})", {"n": module_name, "fp": str(py_file)})
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    fk = f"{module_name}.{node.name}"
                    conn.execute("MERGE (:Function {name: $n, file: $f, line: $l})", {"n": fk, "f": str(py_file), "l": node.lineno})
                    conn.execute("MATCH (f:Function),(m:Module) WHERE f.name=$fn AND m.name=$mn MERGE (f)-[:DEFINED_IN]->(m)", {"fn": fk, "mn": module_name})
                    for child in ast.walk(node):
                        if isinstance(child, ast.Call) and hasattr(child.func, 'id'):
                            cid = child.func.id
                            conn.execute("MERGE (:Function {name: $n, file: '', line: 0})", {"n": cid})
                            conn.execute("MATCH (a:Function),(b:Function) WHERE a.name=$a AND b.name=$b MERGE (a)-[:CALLS]->(b)", {"a": fk, "b": cid})
        except Exception:
            continue
    print("✅ สร้าง Graph DB (Kuzu) สำเร็จ!")

if __name__ == "__main__":
    # ใส่ชื่อโฟลเดอร์ Dataset ของคุณที่นี่
    build_databases("my_dataset")