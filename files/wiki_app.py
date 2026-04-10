#!/usr/bin/env python3
"""
LLM Wiki — App de escritorio
Conecta con LM Studio local para construir una wiki personal orientada a inteligencia y acción.
"""

import base64
import json
import re
import shutil
import subprocess
import threading
import tkinter as tk
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

# Importar inteligencia modular
from wiki_utils import slugify, extract_metadata, parse_json_response

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
MODEL_NAME = "qwen/qwen3.5-9b"
APP_DIR = Path(__file__).resolve().parent
WIKI_DIR = APP_DIR / "wiki"
RAW_DIR = APP_DIR / "raw"
RAW_SOURCES_DIR = RAW_DIR / "fuentes-originales"
RAW_ASSETS_DIR = RAW_DIR / "assets"
SCHEMA_FILE = APP_DIR / "wiki_schema.md"
DOCS_FILE = APP_DIR / "APP_DOCUMENTATION.md"
ROOT_README = APP_DIR.parent / "README.md"

FILE_LOCK = threading.Lock()

SECTION_ORDER = [
    "dashboard", "fuentes", "senales", "claims", "narrativas", "hipotesis",
    "escenarios", "acciones", "temas", "entidades", "conceptos", "consultas",
    "templates", "otros"
]

DEFAULT_SCHEMA = """Sos un asistente especializado en mantener una wiki personal generalista orientada a inteligencia y acción.
La fecha de hoy es __TODAY__ (__TIME__ hs). Usá SIEMPRE esta fecha en logs, ingests y respuestas.
Respondé DIRECTAMENTE con JSON válido.
"""

# --- UTILIDADES DE ARCHIVO Y RUTAS ---

def ensure_text_file(path: Path, content: str):
    if not path.exists():
        path.write_text(content, encoding="utf-8")

def ensure_dirs():
    for directory in [
        WIKI_DIR, RAW_DIR, RAW_SOURCES_DIR, RAW_ASSETS_DIR,
        WIKI_DIR / "fuentes", WIKI_DIR / "senales", WIKI_DIR / "claims",
        WIKI_DIR / "narrativas", WIKI_DIR / "hipotesis", WIKI_DIR / "escenarios",
        WIKI_DIR / "acciones", WIKI_DIR / "temas", WIKI_DIR / "entidades",
        WIKI_DIR / "conceptos", WIKI_DIR / "consultas", WIKI_DIR / "templates"
    ]:
        directory.mkdir(parents=True, exist_ok=True)
    
    ensure_text_file(WIKI_DIR / "index.md", "# Índice de la Wiki\n\n*Vacío — ingresá tu primera fuente.*\n")
    ensure_text_file(WIKI_DIR / "dashboard.md", "# Radar\n\n*Sin actividad todavía.*\n")
    ensure_text_file(WIKI_DIR / "log.md", "# Log de operaciones\n\n")
    ensure_text_file(SCHEMA_FILE, DEFAULT_SCHEMA)

def load_schema() -> str:
    hoy = datetime.now().strftime("%Y-%m-%d")
    hora = datetime.now().strftime("%H:%M")
    schema = SCHEMA_FILE.read_text(encoding="utf-8")
    return schema.replace("__TODAY__", hoy).replace("__TIME__", hora)

def wiki_relpath(path: Path) -> str:
    try:
        return path.relative_to(APP_DIR).as_posix()
    except:
        return path.name

def extract_title(path: Path, content: str) -> str:
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("-", " ").title()

def extract_summary(content: str) -> str:
    for line in content.splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#") or clean.startswith("|") or clean == "---":
            continue
        clean = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", clean)
        return clean[:180]
    return "Sin resumen todavía."

def iter_wiki_pages():
    for path in sorted(WIKI_DIR.rglob("*.md")):
        if path.name in ("index.md", "log.md", "dashboard.md") or "templates" in str(path):
            continue
        yield path

# --- LÓGICA DE NEGOCIO / ORQUESTACIÓN ---

def build_relevant_context(query: str, limit: int = 12) -> str:
    terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
    ranked = []
    for path in iter_wiki_pages():
        content = path.read_text(encoding="utf-8")
        score = sum(content.lower().count(t) for t in terms)
        if score > 0: ranked.append((score, path))
    ranked.sort(key=lambda x: -x[0])
    
    parts = []
    for _, path in ranked[:limit]:
        parts.append(f"### {wiki_relpath(path)}\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(parts)

def build_page_catalog() -> str:
    lines = ["# Catálogo"]
    for path in iter_wiki_pages():
        lines.append(f"- [[{path.stem}]]")
    return "\n".join(lines)

def rebuild_index():
    lines = ["# Índice", "", "- [Radar](dashboard.md)", "- [Log](log.md)\n"]
    for bucket in SECTION_ORDER:
        if bucket == "dashboard" or bucket == "otros": continue
        folder = WIKI_DIR / bucket
        files = list(folder.glob("*.md"))
        if files:
            lines.append(f"## {bucket.title()}")
            for f in sorted(files):
                lines.append(f"- [[{f.stem}]]")
    (WIKI_DIR / "index.md").write_text("\n".join(lines), encoding="utf-8")

def rebuild_dashboard():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = ["# Radar", f"\n*Actualizado: {timestamp}*\n", "## Estado"]
    for bucket in SECTION_ORDER:
        if bucket == "dashboard": continue
        count = len(list((WIKI_DIR / bucket).glob("*.md")))
        lines.append(f"- {bucket.title()}: {count}")
    (WIKI_DIR / "dashboard.md").write_text("\n".join(lines), encoding="utf-8")

def append_log_entry(kind: str, title: str, details: list[str]):
    log_path = WIKI_DIR / "log.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## [{timestamp}] {kind} | {title}\n" + "\n".join(f"- {d}" for d in details) + "\n"
    with FILE_LOCK:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)

def archive_source(text: str, file_path: str | None) -> Path:
    ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    if file_path:
        src = Path(file_path)
        dest = RAW_SOURCES_DIR / f"{ts}-{src.name}"
        shutil.copy2(src, dest)
        return dest
    dest = RAW_SOURCES_DIR / f"{ts}-nota.md"
    dest.write_text(text, encoding="utf-8")
    return dest

def save_pages(pages: list[dict]) -> list[tuple[Path, float]]:
    saved = []
    for p in pages:
        full_path = APP_DIR / p["ruta"]
        full_path.parent.mkdir(parents=True, exist_ok=True)
        if full_path.exists():
            shutil.copy2(full_path, full_path.with_suffix(".md.bak"))
        full_path.write_text(p["contenido"], encoding="utf-8")
        saved.append((full_path, float(p.get("confidence", 0.7))))
    return saved

def call_lm_studio(messages: list, timeout: int = 180) -> str:
    payload = json.dumps({"model": MODEL_NAME, "messages": messages, "temperature": 0.2}).encode("utf-8")
    req = urllib.request.Request(LM_STUDIO_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())["choices"][0]["message"]["content"]

def process_ingest_source(text: str, path: str | None = None) -> tuple[list, str, Path]:
    archived = archive_source(text, path)
    
    # Resolver orfandad básica
    all_p = {p.stem for p in iter_wiki_pages()}
    refs = set()
    for p in iter_wiki_pages():
        refs.update(re.findall(r"\[\[(.*?)\]\]", p.read_text(encoding="utf-8")))
    orphans = sorted(list(all_p - {r.split("|")[0] for r in refs}))[:15]
    
    sys_p = load_schema()
    if orphans:
        sys_p += "\n\nOBJETIVOS DE CONECTIVIDAD:\n- " + "\n- ".join(f"[[{o}]]" for o in orphans)
    
    ctx = build_relevant_context(text[:500])
    user_p = f"Ingerir fuente:\n{text}\n\n---\nContexto:\n{ctx}"
    
    raw = call_lm_studio([{"role": "system", "content": sys_p}, {"role": "user", "content": user_p}])
    result = parse_json_response(raw)
    saved = save_pages(result.get("paginas", []))
    
    append_log_entry("ingest", archived.name, [f"Páginas creadas: {len(saved)}"])
    rebuild_index()
    rebuild_dashboard()
    return saved, result.get("resumen", ""), archived

# --- INTERFAZ GRÁFICA ---

BG = "#0d1117"; BG2 = "#161b22"; BG3 = "#21262d"; ACCENT = "#f0b429"; FG = "#e6edf3"; FG2 = "#8b949e"
FONT_UI = ("Segoe UI", 10); FONT_MONO = ("Courier New", 10)

class WikiApp(tk.Tk):
    def __init__(self):
        super().__init__()
        ensure_dirs()
        self.title("LLM Wiki")
        self.geometry("1100x700")
        self.configure(bg=BG)
        self._current_file = None
        self._consulta_pendiente = None
        self._build_ui()
        self._refresh_tree()

    def _build_ui(self):
        self.columnconfigure(1, weight=1); self.rowconfigure(0, weight=1)
        
        # Sidebar
        left = tk.Frame(self, bg=BG2, width=250); left.grid(row=0, column=0, sticky="nsew")
        left.grid_propagate(False)
        
        tk.Label(left, text="LLM Wiki", font=("Segoe UI", 12, "bold"), bg=BG2, fg=ACCENT).pack(pady=10)
        
        tk.Button(left, text="＋ Ingerir", command=self._open_ingest, bg=ACCENT, fg=BG).pack(fill="x", padx=10, pady=5)
        tk.Button(left, text="🔍 Consultar", command=self._open_query, bg=BG3, fg=FG).pack(fill="x", padx=10, pady=5)
        tk.Button(left, text="📡 Radar", command=self._open_dashboard, bg=BG3, fg=FG).pack(fill="x", padx=10, pady=5)
        
        self.tree = ttk.Treeview(left, show="tree")
        self.tree.pack(fill="both", expand=True, padx=5, pady=10)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        
        # Main Area
        right = tk.Frame(self, bg=BG); right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1); right.rowconfigure(1, weight=1)
        
        top = tk.Frame(right, bg=BG3, height=40); top.grid(row=0, column=0, sticky="ew")
        self.lbl_title = tk.Label(top, text="Bienvenido", bg=BG3, fg=FG2, padx=10)
        self.lbl_title.pack(side="left")
        
        self.btn_save = tk.Button(top, text="💾 Guardar", command=self._save_file, bg="#238636", fg="white")
        self.btn_save.pack(side="right", padx=10)
        
        self.btn_archive = tk.Button(top, text="📥 Archivar", command=self._archive_query, bg="#388bfd", fg="white")
        
        self.editor = scrolledtext.ScrolledText(right, bg=BG2, fg=FG, font=FONT_MONO, insertbackground="white")
        self.editor.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        self.status = tk.Label(right, text="Listo.", bg=BG, fg=FG2, anchor="w"); self.status.grid(row=2, column=0, sticky="ew", padx=10)

    def _set_status(self, txt): self.status.config(text=txt); self.update_idletasks()

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        root = self.tree.insert("", "end", text="wiki", open=True)
        for folder in SECTION_ORDER:
            if folder == "dashboard": continue
            f_node = self.tree.insert(root, "end", text=folder)
            for f in sorted((WIKI_DIR / folder).glob("*.md")):
                self.tree.insert(f_node, "end", text=f.name, values=[str(f)])

    def _on_tree_select(self, _):
        sel = self.tree.selection()
        if not sel: return
        vals = self.tree.item(sel[0], "values")
        if not vals: return
        path = Path(vals[0])
        if path.is_file():
            self._current_file = path
            self.lbl_title.config(text=path.name)
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", path.read_text(encoding="utf-8"))
            self.btn_archive.pack_forget()
            self.btn_save.pack(side="right", padx=10)

    def _save_file(self):
        if self._current_file:
            self._current_file.write_text(self.editor.get("1.0", "end-1c"), encoding="utf-8")
            self._set_status(f"Guardado: {self._current_file.name}")

    def _open_dashboard(self):
        rebuild_dashboard()
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", (WIKI_DIR / "dashboard.md").read_text(encoding="utf-8"))
        self.lbl_title.config(text="Dashboard")

    def _open_ingest(self):
        win = tk.Toplevel(self); win.title("Ingerir"); win.geometry("400x300")
        txt = scrolledtext.ScrolledText(win); txt.pack(fill="both", expand=True)
        def go():
            content = txt.get("1.0", "end").strip()
            win.destroy()
            self._set_status("⏳ Ingeriendo...")
            threading.Thread(target=lambda: self._do_ingest_thread(content), daemon=True).start()
        tk.Button(win, text="Procesar", command=go).pack()

    def _do_ingest_thread(self, content):
        try:
            saved, summary, _ = process_ingest_source(content)
            self.after(0, lambda: [self._refresh_tree(), self._set_status(f"✅ {summary}")])
        except Exception as e:
            self.after(0, lambda: self._set_status(f"❌ Error: {e}"))

    def _open_query(self):
        win = tk.Toplevel(self); win.title("Consulta"); win.geometry("400x100")
        ent = tk.Entry(win); ent.pack(fill="x", padx=10, pady=10); ent.focus()
        def go():
            q = ent.get().strip()
            win.destroy()
            self._set_status("⏳ Consultando...")
            threading.Thread(target=lambda: self._do_query_thread(q), daemon=True).start()
        tk.Button(win, text="Preguntar", command=go).pack()

    def _do_query_thread(self, q):
        try:
            ctx = build_relevant_context(q)
            res = call_lm_studio([{"role": "system", "content": load_schema()}, {"role": "user", "content": f"Pregunta: {q}\n\nContexto:\n{ctx}"}])
            data = parse_json_response(res)
            ans = data.get("respuesta", res)
            self.after(0, lambda: self._show_query_result(q, ans, data))
        except Exception as e:
            self.after(0, lambda: self._set_status(f"❌ Error: {e}"))

    def _show_query_result(self, q, ans, data):
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", f"# Consulta: {q}\n\n{ans}")
        self.lbl_title.config(text="Resultado Consulta")
        self._consulta_pendiente = (data.get("titulo_archivo", "consulta"), self.editor.get("1.0", "end"), q)
        self.btn_save.pack_forget()
        self.btn_archive.pack(side="right", padx=10)
        self._set_status("✅ Consulta lista.")

    def _archive_query(self):
        if self._consulta_pendiente:
            title, content, q = self._consulta_pendiente
            path = WIKI_DIR / "consultas" / f"{slugify(title)}.md"
            path.write_text(content, encoding="utf-8")
            append_log_entry("consulta", q, [f"Archivada en {path.name}"])
            self._refresh_tree()
            self.btn_archive.pack_forget()
            self._set_status(f"Archivado: {path.name}")

if __name__ == "__main__":
    app = WikiApp(); app.mainloop()
