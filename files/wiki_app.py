#!/usr/bin/env python3
"""
LLM Wiki — Brain Shell (Premium RAG & Integrity Fixed)
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

# Importar utilidades blindadas
from wiki_utils import slugify, extract_metadata, parse_json_response, VectorEngine

# --- CONSTANTES ---
BG_COLOR = "#121212"
SIDEBAR_BG = "#1E1E1E"
TEXT_BG = "#181818"
FG_COLOR = "#E0E0E0"
ACCENT_COLOR = "#00ADB5"
ACCENT_MUTED = "#393E46"
HIGHTLIGHT = "#00FFF5"
STATUS_BG = "#0D1117"

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
MODEL_NAME = "qwen/qwen3.5-9b"
APP_DIR = Path(__file__).resolve().parent
WIKI_DIR = APP_DIR / "wiki"
RAW_DIR = APP_DIR / "raw"
RAW_SOURCES_DIR = RAW_DIR / "fuentes-originales"
RAW_ASSETS_DIR = RAW_DIR / "assets"
SCHEMA_FILE = APP_DIR / "wiki_schema.md"

FILE_LOCK = threading.Lock()
SECTION_ORDER = ["dashboard", "fuentes", "senales", "claims", "narrativas", "hipotesis", "escenarios", "acciones", "temas", "entidades", "conceptos", "consultas", "templates", "otros"]

# --- FUNCIONES GLOBALES DE ORQUESTACIÓN ---

def load_schema() -> str:
    if SCHEMA_FILE.exists():
        schema = SCHEMA_FILE.read_text(encoding="utf-8")
    else:
        schema = "Sos un asistente de wiki. Respondé en JSON."
    return schema.replace("__TODAY__", datetime.now().strftime("%Y-%m-%d")).replace("__TIME__", datetime.now().strftime("%H:%M"))

def wiki_relpath(path: Path) -> str:
    try: return str(path.relative_to(WIKI_DIR))
    except: return str(path)

def build_relevant_context(seed: str, limit: int = 12) -> str:
    results = []
    seen = set()
    
    # Intentar búsqueda vectorial
    import __main__
    global app
    active_app = getattr(__main__, 'app', None)
    if active_app and hasattr(active_app, 'vector_engine'):
        try:
            v_results = active_app.vector_engine.search(seed, top_k=limit)
            for rel_path, score in v_results:
                if score > 0.5:
                    p = WIKI_DIR / rel_path
                    if p.exists() and p.stem not in seen:
                        results.append(f"### [Relación Semántica: {p.name}]\n{p.read_text(encoding='utf-8')[:3000]}")
                        seen.add(p.stem)
        except Exception as e:
            print(f"⚠️ Error en búsqueda vectorial: {e}")

    # Búsqueda por palabras clave (Complemento)
    keywords = [k.lower() for k in seed.split() if len(k) > 3]
    if len(results) < limit:
        for path in sorted(WIKI_DIR.rglob("*.md")):
            if path.name in ("index.md", "log.md", "dashboard.md"): continue
            if path.stem in seen: continue
            content = path.read_text(encoding="utf-8").lower()
            if any(kw in content or kw in path.stem.lower() for kw in keywords):
                results.append(f"### [Relación Keyword: {path.name}]\n{path.read_text(encoding='utf-8')[:2000]}")
                seen.add(path.stem)
                if len(results) >= limit: break
    
    return "\n\n".join(results)

def rebuild_index():
    sections = {name: [] for name in SECTION_ORDER}
    for path in sorted(WIKI_DIR.rglob("*.md")):
        if path.name in ("index.md", "log.md", "dashboard.md") or "templates" in str(path): continue
        parent = path.parent.name
        bucket = parent if parent in SECTION_ORDER else "otros"
        sections[bucket].append(f"- [[{path.stem}]]")

    lines = ["# Índice de la Wiki", "", "- [Radar](dashboard.md)", "- [Log](log.md)"]
    for bucket in SECTION_ORDER:
        if sections[bucket]:
            lines.append(f"\n## {bucket.upper()}"); lines.extend(sections[bucket])
    (WIKI_DIR / "index.md").write_text("\n".join(lines), encoding="utf-8")

def rebuild_dashboard():
    counts = {b: len(list((WIKI_DIR / b).glob("*.md"))) if (WIKI_DIR / b).exists() else 0 for b in SECTION_ORDER}
    lines = ["# Radar", "", "## Resumen"]
    for b in SECTION_ORDER:
        if b != "dashboard": lines.append(f"- {b.title()}: {counts.get(b, 0)}")
    lines.append(f"\n---\n*Dashboard actualizado: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    (WIKI_DIR / "dashboard.md").write_text("\n".join(lines), encoding="utf-8")

def refresh_compiled_views():
    rebuild_index()
    rebuild_dashboard()

def append_log_entry(kind: str, title: str, details: list[str]):
    log_path = WIKI_DIR / "log.md"
    entry = [f"## [{datetime.now().strftime('%Y-%m-%d %H:%M')}] {kind.upper()} | {title}"] + [f"- {d}" for d in details]
    with FILE_LOCK:
        with open(log_path, "a", encoding="utf-8") as h: h.write("\n" + "\n".join(entry) + "\n")

def call_lm_studio(messages: list) -> str:
    payload = {"model": MODEL_NAME, "messages": messages, "temperature": 0.1, "max_tokens": 32000}
    req = urllib.request.Request(LM_STUDIO_URL, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode())["choices"][0]["message"]["content"]

# --- CLASE DE LA INTERFAZ ---

class WikiApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LLM Wiki - Brain Shell")
        self.geometry("1300x850")
        self.configure(bg=BG_COLOR)
        
        # Estado
        self.vector_engine = VectorEngine(WIKI_DIR)
        self._current_file = None
        self._consulta_activa = None
        
        self._build_styles()
        self._build_ui()
        self.refresh_tree()

    def _build_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("Treeview", background=SIDEBAR_BG, foreground=FG_COLOR, fieldbackground=SIDEBAR_BG, borderwidth=0, font=("Segoe UI", 10))
        s.map("Treeview", background=[("selected", ACCENT_COLOR)])
        s.configure("TPanedwindow", background=BG_COLOR)
        s.configure("TFrame", background=BG_COLOR)
        s.configure("TLabel", background=BG_COLOR, foreground=FG_COLOR)
        s.configure("Accent.TButton", background=ACCENT_COLOR, foreground="white", font=("Segoe UI Bold", 9))
        s.configure("Muted.TButton", background=ACCENT_MUTED, foreground=FG_COLOR, font=("Segoe UI", 9))

    def _build_ui(self):
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Sidebar
        side = ttk.Frame(paned, width=280)
        paned.add(side, weight=1)
        ttk.Label(side, text=" EXPLORADOR", foreground=ACCENT_COLOR, font=("Segoe UI Bold", 10)).pack(fill=tk.X, pady=10, padx=10)
        
        self.tree = ttk.Treeview(side, show="tree")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Editor
        work = ttk.Frame(paned)
        paned.add(work, weight=4)
        
        self.editor = scrolledtext.ScrolledText(work, wrap=tk.WORD, font=("Consolas", 12), bg=TEXT_BG, fg=FG_COLOR, insertbackground=ACCENT_COLOR, borderwidth=0, padx=15, pady=15)
        self.editor.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Actions
        btns = ttk.Frame(work)
        btns.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(btns, text="INGESTAR FUENTE", style="Accent.TButton", command=self.gui_ingest).pack(side=tk.LEFT, padx=5, ipady=3)
        ttk.Button(btns, text="CONSULTA SEMÁNTICA", style="Accent.TButton", command=self.gui_query).pack(side=tk.LEFT, padx=5, ipady=3)
        ttk.Button(btns, text="GUARDAR", style="Muted.TButton", command=self.gui_save).pack(side=tk.RIGHT, padx=5, ipady=3)
        self.btn_archive = ttk.Button(btns, text="ARCHIVAR RESPUESTA", style="Muted.TButton", command=self.gui_archive, state=tk.DISABLED)
        self.btn_archive.pack(side=tk.RIGHT, padx=5, ipady=3)
        
        # Status
        self.st_var = tk.StringVar(value=" READY")
        tk.Label(self, textvariable=self.st_var, bg=STATUS_BG, fg=ACCENT_COLOR, font=("Segoe UI Bold", 9), anchor="w", padx=10, pady=4).pack(fill=tk.X)

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for b in SECTION_ORDER:
            node = self.tree.insert("", "end", text=f"📂 {b.upper()}", open=(b=="dashboard"))
            path = WIKI_DIR / b
            if path.exists():
                for f in sorted(path.glob("*.md")):
                    self.tree.insert(node, "end", text=f"  📄 {f.name}", values=(str(f),))

    def _on_tree_select(self, e):
        sel = self.tree.selection()
        if sel and self.tree.item(sel[0])["values"]:
            self.open_file(Path(self.tree.item(sel[0])["values"][0]))

    def open_file(self, path: Path):
        self._current_file = path
        self.editor.delete("1.0", tk.END)
        self.editor.insert(tk.END, path.read_text(encoding="utf-8"))
        self.st_var.set(f" EDITANDO: {path.name.upper()}")
        self.btn_archive.config(state=tk.DISABLED)

    def gui_save(self):
        if not self._current_file: return
        content = self.editor.get("1.0", tk.END).strip()
        with FILE_LOCK:
            self._current_file.write_text(content, encoding="utf-8")
            self.vector_engine.update_page(wiki_relpath(self._current_file), content)
        self.st_var.set(" ✅ GUARDADO")
        refresh_compiled_views(); self.refresh_tree()

    def gui_ingest(self):
        f = filedialog.askopenfilename()
        if f: 
            self.st_var.set(" 🧠 PENSANDO...")
            threading.Thread(target=self._proc_ingest, args=(f,), daemon=True).start()

    def _proc_ingest(self, file_path):
        try:
            path = Path(file_path); text = ""
            if path.suffix.lower() == ".pdf":
                from pdfminer.high_level import extract_text; text = extract_text(str(path))
            else: text = path.read_text(encoding="utf-8")
            
            # Contexto e Ingesta
            ctx = build_relevant_context(path.name + " " + text[:400])
            msgs = [{"role": "system", "content": load_schema()}, {"role": "user", "content": f"Archivo: {path.name}\n\nContenido:\n{text}\n\nContexto:\n{ctx}"}]
            
            res = parse_json_response(call_lm_studio(msgs))
            saved = []
            for p in res.get("paginas", []):
                dest = APP_DIR / p["ruta"]; dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(p["contenido"], encoding="utf-8")
                self.vector_engine.update_page(wiki_relpath(dest), p["contenido"])
                saved.append(dest.name)
            
            append_log_entry("ingest", path.name, [f"Creadas: {len(saved)}"])
            refresh_compiled_views()
            self.after(0, lambda: [self.refresh_tree(), self.st_var.set(" ✅ INGESTA OK")])
        except Exception as e: self.after(0, lambda: messagebox.showerror("Error", str(e)))

    def gui_query(self):
        q = filedialog.askstring("Consulta", "Pregunta:")
        if q:
            self.st_var.set(" 🔍 BUSCANDO...")
            threading.Thread(target=self._proc_query, args=(q,), daemon=True).start()

    def _proc_query(self, query):
        try:
            ctx = build_relevant_context(query, limit=12)
            msgs = [{"role": "system", "content": load_schema()}, {"role": "user", "content": f"Pregunta: {query}\n\nContexto:\n{ctx}"}]
            res = parse_json_response(call_lm_studio(msgs))
            self._consulta_activa = res
            self.after(0, lambda: [self.editor.delete("1.0", tk.END), self.editor.insert(tk.END, res["respuesta"]), self.st_var.set(" ✅ LISTO"), self.btn_archive.config(state=tk.NORMAL)])
        except Exception as e: self.after(0, lambda: messagebox.showerror("Error", str(e)))

    def gui_archive(self):
        if self._consulta_activa:
            res = self._consulta_activa
            title = slugify(res.get("titulo_archivo", "consulta"))
            path = WIKI_DIR / "consultas" / f"{title}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(res["respuesta"], encoding="utf-8")
            self.vector_engine.update_page(wiki_relpath(path), res["respuesta"])
            refresh_compiled_views(); self.refresh_tree()
            self.st_var.set(f" ✅ ARCHIVADO: {path.name}"); self.btn_archive.config(state=tk.DISABLED)

if __name__ == "__main__":
    app = WikiApp(); app.mainloop()
