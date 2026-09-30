import ast
import pathlib
import shutil
from collections import defaultdict
from dataclasses import dataclass

MODEL_EMBED = "nomic-embed-text"
VECTOR_DB_PATH = "vector_db"
GRAPH_DB_PATH = "graph_db"

# โฟลเดอร์ที่ไม่ต้องอ่าน (migrations ของ Django เป็นแค่ noise)
SKIP_DIRS = {"venv", ".venv", "env", "__pycache__", ".git", "node_modules",
             "site-packages", "migrations", "staticfiles", "media"}
# ไฟล์ที่ไม่ใส่ลง Vector DB เพราะมี SECRET_KEY / config (กัน LLM เอาไปตอบ)
SKIP_CHUNK_FILES = {"settings.py"}
MAX_MODULE_CHUNK = 3000

FUNC_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)
URL_FUNCS = {"path", "re_path", "url"}


# =====================================================================
# Data classes
# =====================================================================
@dataclass
class ParsedFile:
    module: str            # เช่น "booking_bmt.views"
    path: pathlib.Path
    source: str
    tree: ast.AST
    is_package: bool       # เป็น __init__.py หรือไม่ (ใช้คำนวณ relative import)


@dataclass
class FuncInfo:
    full: str              # "booking_bmt.models::Booking.save"  (คีย์ไม่ซ้ำ)
    qualname: str          # "Booking.save"
    short: str             # "save"
    module: str
    cls: str | None        # คลาสที่ครอบอยู่ทันที (None = ฟังก์ชันปกติ)
    pf: ParsedFile
    node: ast.AST


@dataclass
class Imports:
    modules: set           # โมดูลในโปรเจกต์ที่ไฟล์นี้ import
    aliases: dict          # ชื่อในไฟล์ -> โมดูล        (import x / from pkg import module)
    names: dict            # ชื่อในไฟล์ -> (โมดูล, ชื่อเดิม)  (from mod import name)


# =====================================================================
# อ่านไฟล์ / เดินหา definition
# =====================================================================
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
        is_package = parts[-1] == "__init__" and len(parts) > 1
        if is_package:
            parts = parts[:-1]
        files.append(ParsedFile(".".join(parts), py_file, source, tree, is_package))
    return files


def iter_defs(node, prefix="", cls=None):
    """เดินหา function/class พร้อมชื่อเต็ม (Class.method) และคลาสที่ครอบอยู่"""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, FUNC_TYPES):
            qual = f"{prefix}{child.name}"
            yield "func", qual, child, cls
            yield from iter_defs(child, qual + ".", None)
        elif isinstance(child, ast.ClassDef):
            qual = f"{prefix}{child.name}"
            yield "class", qual, child, cls
            yield from iter_defs(child, qual + ".", qual)
        else:
            yield from iter_defs(child, prefix, cls)


def walk_own(func_node):
    """เดินโหนดในฟังก์ชัน โดยไม่ลงไปในฟังก์ชัน/คลาสซ้อนใน"""
    stack = list(ast.iter_child_nodes(func_node))
    while stack:
        n = stack.pop()
        if isinstance(n, FUNC_TYPES + (ast.ClassDef,)):
            continue
        yield n
        stack.extend(ast.iter_child_nodes(n))


def analyze_imports(pf: ParsedFile, modules: set) -> Imports:
    """รองรับทั้ง absolute และ relative import (from .x import y / from . import x)"""
    pkg = pf.module if pf.is_package else pf.module.rpartition(".")[0]
    imported, aliases, names = set(), {}, {}
    for node in ast.walk(pf.tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name in modules:
                    imported.add(a.name)
                    aliases[a.asname or a.name] = a.name
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg.split(".") if pkg else []
                up = node.level - 1
                if up:
                    base = base[: len(base) - up] if up <= len(base) else []
                target = ".".join(base + (node.module.split(".") if node.module else []))
            else:
                target = node.module or ""
            for a in node.names:
                local = a.asname or a.name
                sub = f"{target}.{a.name}" if target else a.name
                if sub in modules:                 # from pkg import module
                    imported.add(sub)
                    aliases[local] = sub
                elif target in modules:            # from module import name
                    imported.add(target)
                    names[local] = (target, a.name)
    imported.discard(pf.module)
    return Imports(imported, aliases, names)


# =====================================================================
# Project index: รวมทุกอย่างไว้ที่เดียว แล้วใช้ resolve การเรียก / URL
# =====================================================================
class Project:
    def __init__(self, files: list[ParsedFile]):
        self.files = files
        self.modules = {pf.module for pf in files}
        self.funcs: dict[str, FuncInfo] = {}
        self.classes: dict[tuple, tuple] = {}   # (module, qual) -> (pf, node)
        for pf in files:
            for kind, qual, node, cls in iter_defs(pf.tree):
                if kind == "func":
                    full = f"{pf.module}::{qual}"
                    # ถ้าประกาศชื่อซ้ำ ตัวหลังทับตัวแรก (เหมือนที่ Python ทำจริงตอนรัน)
                    self.funcs[full] = FuncInfo(full, qual, node.name, pf.module, cls, pf, node)
                else:
                    self.classes.setdefault((pf.module, qual), (pf, node))
        self.imports = {pf.module: analyze_imports(pf, self.modules) for pf in files}
        self.methods_by_short = defaultdict(list)
        for f in self.funcs.values():
            if f.cls:
                self.methods_by_short[f.short].append(f)

    # ---------- หา class / callable ----------
    def resolve_class(self, module, name):
        imp = self.imports[module]
        if name in imp.names and imp.names[name] in self.classes:
            return imp.names[name]
        if (module, name) in self.classes:
            return (module, name)
        return None

    def find_method(self, module, cls, method, seen=None):
        """หาเมธอดในคลาส ถ้าไม่มีให้ไล่ขึ้นไปตามคลาสแม่ (เฉพาะที่อยู่ในโปรเจกต์)"""
        seen = seen if seen is not None else set()
        if (module, cls) in seen:
            return None
        seen.add((module, cls))
        t = f"{module}::{cls}.{method}"
        if t in self.funcs:
            return t
        entry = self.classes.get((module, cls))
        for b in (entry[1].bases if entry else []):
            if isinstance(b, ast.Name):
                c = self.resolve_class(module, b.id)
                if c:
                    found = self.find_method(c[0], c[1], method, seen)
                    if found:
                        return found
        return None

    def _callable(self, module, name):
        t = f"{module}::{name}"
        if t in self.funcs and self.funcs[t].cls is None:
            return [t]
        init = f"{module}::{name}.__init__"          # Order(...) -> Order.__init__
        if (module, name) in self.classes and init in self.funcs:
            return [init]
        return []

    def local_var_types(self, f: FuncInfo) -> dict:
        """เดาชนิดตัวแปรแบบง่ายๆ: x = Cls(...) และ parameter ที่มี type hint"""
        types = {}
        args = f.node.args
        for a in args.posonlyargs + args.args + args.kwonlyargs:
            if isinstance(a.annotation, ast.Name):
                c = self.resolve_class(f.module, a.annotation.id)
                if c:
                    types[a.arg] = c
        for n in walk_own(f.node):
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name):
                c = self.resolve_class(f.module, n.value.func.id)
                if c:
                    for t in n.targets:
                        if isinstance(t, ast.Name):
                            types[t.id] = c
        return types

    # ---------- resolve การเรียกฟังก์ชัน ----------
    def resolve_call(self, f: FuncInfo, call: ast.Call, var_types: dict) -> list[str]:
        fn, imp = call.func, self.imports[f.module]

        if isinstance(fn, ast.Name):                       # foo()
            name = fn.id
            nested = f"{f.full}.{name}"
            if nested in self.funcs:
                return [nested]
            if name in imp.names:
                return self._callable(*imp.names[name])
            return self._callable(f.module, name)

        if not isinstance(fn, ast.Attribute):
            return []
        method, recv = fn.attr, fn.value

        # super().x() ไม่ใช่การเรียกตัวเอง
        if isinstance(recv, ast.Call) and isinstance(recv.func, ast.Name) and recv.func.id == "super":
            return []

        if isinstance(recv, ast.Name):
            r = recv.id
            if r in ("self", "cls") and f.cls:
                t = self.find_method(f.module, f.cls, method)
                if t:
                    return [t]
            elif r in imp.aliases:                          # module.func()
                return self._callable(imp.aliases[r], method)
            else:
                c = var_types.get(r) or self.resolve_class(f.module, r)
                if c:                                       # รู้คลาสแล้ว: ไม่เจอเมธอด = ของ framework
                    t = self.find_method(c[0], c[1], method)
                    return [t] if t else []

        # ไม่รู้ชนิด: เชื่อมเฉพาะเมื่อมีเมธอดชื่อนี้ "ตัวเดียว" ในโมดูลที่ไฟล์นี้มองเห็น
        visible = {f.module} | self.imports[f.module].modules
        cands = [m.full for m in self.methods_by_short.get(method, [])
                 if m.module in visible and m.full != f.full]   # ไม่นับตัวเอง (เช่น user.save() ใน save())
        return cands if len(cands) == 1 else []

    def build_calls(self) -> set:
        calls = set()
        for f in self.funcs.values():
            var_types = self.local_var_types(f)
            for n in walk_own(f.node):
                if isinstance(n, ast.Call):
                    for t in self.resolve_call(f, n, var_types):
                        calls.add((f.full, t))
        return calls

    def build_imports(self) -> set:
        return {(m, t) for m, imp in self.imports.items() for t in imp.modules}

    # ---------- Django URLs ----------
    def build_routes(self) -> list[tuple]:
        """คืน [(full_path, url_name, view_full_name)] โดยต่อ prefix จาก include() ให้ครบ"""
        routes, includes = defaultdict(list), defaultdict(list)
        for pf in self.files:
            imp = self.imports[pf.module]
            elements = []
            for node in ast.walk(pf.tree):
                if isinstance(node, (ast.Assign, ast.AugAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    if any(isinstance(t, ast.Name) and t.id == "urlpatterns" for t in targets):
                        elements += _url_elements(node.value)
            for el in elements:
                if not isinstance(el, ast.Call):
                    continue
                fname = el.func.id if isinstance(el.func, ast.Name) else getattr(el.func, "attr", "")
                if fname not in URL_FUNCS or len(el.args) < 2:
                    continue
                if not (isinstance(el.args[0], ast.Constant) and isinstance(el.args[0].value, str)):
                    continue
                pattern, target = el.args[0].value, el.args[1]
                url_name = next((k.value.value for k in el.keywords
                                 if k.arg == "name" and isinstance(k.value, ast.Constant)), "")

                if isinstance(target, ast.Call) and getattr(target.func, "id", "") == "include":
                    if target.args and isinstance(target.args[0], ast.Constant):
                        child = target.args[0].value
                        if child in self.modules:
                            includes[pf.module].append((pattern, child))
                    continue

                view = None
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                    m = imp.aliases.get(target.value.id)
                    view = f"{m}::{target.attr}" if m else None      # views.func
                elif isinstance(target, ast.Name):
                    m, o = imp.names.get(target.id, (pf.module, target.id))
                    view = f"{m}::{o}"                                # func (from .views import func)
                if view in self.funcs and self.funcs[view].cls is None:
                    routes[pf.module].append((pattern, url_name, view))

        children = {c for lst in includes.values() for _, c in lst}
        roots = [m for m in set(routes) | set(includes) if m not in children]
        result = []

        def dfs(mod, prefix, stack):
            for pat, url_name, view in routes.get(mod, []):
                result.append(("/" + prefix + pat, url_name, view))
            for pat, child in includes.get(mod, []):
                if child not in stack:
                    dfs(child, prefix + pat, stack + (child,))

        for r in sorted(roots):
            dfs(r, "", (r,))
        return result


def _url_elements(value):
    if isinstance(value, ast.List):
        return list(value.elts)
    if isinstance(value, ast.BinOp):
        return _url_elements(value.left) + _url_elements(value.right)
    return []


# =====================================================================
# Vector DB
# =====================================================================
def _segment(pf, node):
    return ast.get_source_segment(pf.source, node) or ""


def _class_chunk(pf, qual, node):
    """ส่วนหัวคลาส + field + class Meta (ไม่รวมตัวเมธอด) เหมาะกับการตอบเรื่อง model"""
    bases = ", ".join(ast.unparse(b) for b in node.bases)
    parts = [f"class {qual}({bases})"]
    parts += [_segment(pf, s) for s in node.body if not isinstance(s, FUNC_TYPES)]
    methods = [s.name for s in node.body if isinstance(s, FUNC_TYPES)]
    if methods:
        parts.append("# methods: " + ", ".join(methods))
    return "\n".join(p for p in parts if p)


def _module_chunk(pf):
    """docstring + ค่าคงที่ระดับโมดูล + urlpatterns"""
    keep = [s for s in pf.tree.body
            if isinstance(s, (ast.Assign, ast.AnnAssign))
            or (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str))]
    return "\n".join(_segment(pf, s) for s in keep)[:MAX_MODULE_CHUNK]


def build_vector_db(project: Project):
    from langchain_community.vectorstores import FAISS
    from langchain_ollama import OllamaEmbeddings
    from langchain_core.documents import Document

    docs = []
    for f in project.funcs.values():
        start = min([d.lineno for d in f.node.decorator_list] + [f.node.lineno])   # รวม @decorator
        lines = f.pf.source.split("\n")[start - 1: f.node.end_lineno]
        docs.append(Document(
            page_content="\n".join(lines),
            metadata={"kind": "method" if f.cls else "function", "function": f.qualname,
                      "module": f.module, "file": str(f.pf.path), "line": f.node.lineno},
        ))
    for (module, qual), (pf, node) in project.classes.items():
        if pf.path.name in SKIP_CHUNK_FILES:
            continue
        docs.append(Document(
            page_content=_class_chunk(pf, qual, node),
            metadata={"kind": "class", "function": qual, "module": module,
                      "file": str(pf.path), "line": node.lineno},
        ))
    for pf in project.files:
        if pf.path.name in SKIP_CHUNK_FILES:
            continue
        text = _module_chunk(pf)
        if text.strip():
            docs.append(Document(
                page_content=f"# module {pf.module}\n{text}",
                metadata={"kind": "module", "function": f"<{pf.module}>", "module": pf.module,
                          "file": str(pf.path), "line": 1},
            ))

    vp = pathlib.Path(VECTOR_DB_PATH)
    if not docs:
        print("⚠️ ไม่พบโค้ดเลย ข้ามการสร้าง Vector DB")
        if vp.exists():
            shutil.rmtree(vp)
        return

    print(f"เจอ {len(docs)} chunks (functions/classes/modules) กำลังสร้าง Vector DB...")
    vs = FAISS.from_documents(docs, OllamaEmbeddings(model=MODEL_EMBED))
    vs.save_local(VECTOR_DB_PATH)
    print("✅ สร้าง Vector DB (FAISS) สำเร็จ!")


# =====================================================================
# Graph DB
# =====================================================================
def _remove_old_graph():
    for p in (pathlib.Path(GRAPH_DB_PATH), pathlib.Path(GRAPH_DB_PATH + ".wal")):
        if p.exists():
            shutil.rmtree(p) if p.is_dir() else p.unlink()


def build_graph_db(project: Project):
    import kuzu

    print("กำลังสร้าง Graph DB...")
    _remove_old_graph()
    db = kuzu.Database(GRAPH_DB_PATH)
    conn = kuzu.Connection(db)
    conn.execute("CREATE NODE TABLE Function (name STRING, qualname STRING, file STRING, line INT64, PRIMARY KEY (name))")
    conn.execute("CREATE NODE TABLE Module (name STRING, filepath STRING, PRIMARY KEY (name))")
    conn.execute("CREATE NODE TABLE Route (name STRING, url_name STRING, PRIMARY KEY (name))")
    conn.execute("CREATE REL TABLE CALLS (FROM Function TO Function)")
    conn.execute("CREATE REL TABLE DEFINED_IN (FROM Function TO Module)")
    conn.execute("CREATE REL TABLE IMPORTS (FROM Module TO Module)")
    conn.execute("CREATE REL TABLE ROUTES_TO (FROM Route TO Function)")

    for pf in project.files:
        conn.execute("CREATE (:Module {name: $n, filepath: $p})", {"n": pf.module, "p": str(pf.path)})
    for f in project.funcs.values():
        conn.execute(
            "CREATE (:Function {name: $n, qualname: $q, file: $f, line: $l})",
            {"n": f.full, "q": f.qualname, "f": str(f.pf.path), "l": f.node.lineno},
        )
        conn.execute(
            "MATCH (a:Function {name: $a}), (m:Module {name: $m}) CREATE (a)-[:DEFINED_IN]->(m)",
            {"a": f.full, "m": f.module},
        )

    calls = project.build_calls()
    for a, b in calls:
        conn.execute("MATCH (a:Function {name: $a}), (b:Function {name: $b}) CREATE (a)-[:CALLS]->(b)",
                     {"a": a, "b": b})

    imports = project.build_imports()
    for a, b in imports:
        conn.execute("MATCH (a:Module {name: $a}), (b:Module {name: $b}) CREATE (a)-[:IMPORTS]->(b)",
                     {"a": a, "b": b})

    routes = project.build_routes()
    seen_routes = set()
    for path, url_name, view in routes:
        if path not in seen_routes:
            conn.execute("CREATE (:Route {name: $n, url_name: $u})", {"n": path, "u": url_name})
            seen_routes.add(path)
        conn.execute("MATCH (r:Route {name: $r}), (f:Function {name: $f}) CREATE (r)-[:ROUTES_TO]->(f)",
                     {"r": path, "f": view})

    print(f"✅ สร้าง Graph DB (Kuzu) สำเร็จ! {len(project.funcs)} functions, {len(calls)} calls, "
          f"{len(imports)} imports, {len(seen_routes)} routes")


def resolve_root(source_directory: str):
    """หาโฟลเดอร์ทั้งจากที่รันอยู่ และจากตำแหน่งไฟล์ setup.py"""
    for c in (pathlib.Path(source_directory), pathlib.Path(__file__).resolve().parent / source_directory):
        if c.is_dir():
            return c.resolve()
    return None


def build_databases(source_directory: str):
    root = resolve_root(source_directory)
    if root is None:
        print(f"❌ ไม่พบโฟลเดอร์ '{source_directory}'")
        print(f"   โฟลเดอร์ที่รันอยู่ตอนนี้: {pathlib.Path.cwd()}")
        print("   ตรวจว่าชื่อถูกต้อง และโฟลเดอร์อยู่ข้าง setup.py  (เช่น: python setup.py BMT-Django)")
        return
    print(f"กำลังสแกนโค้ดในโฟลเดอร์: {root}")
    files = load_files(root)
    if not files:
        print(f"❌ ไม่พบไฟล์ .py ในโฟลเดอร์นี้ (ข้าม: {', '.join(sorted(SKIP_DIRS))})")
        print("   ตรวจว่าชี้ไปที่โฟลเดอร์ที่มีโค้ด Python จริง ไม่ใช่โฟลเดอร์ว่าง")
        return
    project = Project(files)
    print(f"พบ {len(files)} ไฟล์ .py, {len(project.funcs)} ฟังก์ชัน, {len(project.classes)} คลาส")
    build_vector_db(project)
    build_graph_db(project)


if __name__ == "__main__":
    import sys
    build_databases(sys.argv[1] if len(sys.argv) > 1 else "my_dataset")