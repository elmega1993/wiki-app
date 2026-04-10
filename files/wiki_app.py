#!/usr/bin/env python3
"""
LLM Wiki — Brain Shell
Ecosistema de conocimiento estructurado con búsqueda semántica y trazabilidad.
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

# Utilidades Lógicas y Vectoriales
from wiki_utils import slugify, extract_metadata, parse_json_response, VectorEngine

# Configuración
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

# --- FUNCIONES DE SOPORTE ---

def load_schema() -> str:
    if SCHEMA_FILE.exists():
        schema = SCHEMA_FILE.read_text(encoding="utf-8")
    else:
        schema = "Sos un asistente de wiki personal. Respondé en JSON." # Fallback
    
    hoy = datetime.now().strftime("%Y-%m-%d")
    hora = datetime.now().strftime("%H:%M")
    return schema.replace("__TODAY__", hoy).replace("__TIME__", hora)

def wiki_relpath(path: Path) -> str:
    try:
        return str(path.relative_to(WIKI_DIR))
    except ValueError:
        return str(path)

def bucket_for_path(path: Path) -> str:
    parent = path.parent.name
    return parent if parent in SECTION_ORDER else "otros"

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
        if path.name in ("index.md", "log.md", "dashboard.md") or "templates" in str(path) or "backup" in str(path):
            continue
        yield path

# --- LÓGICA DE CONTEXTO Y BÚSQUEDA ---

def build_relevant_context(seed: str, limit: int = 10) -> str:
    results = []
    seen = set()
    
    # IMPORTANTE: Acceso a la instancia global de la app para el motor vectorial
    import __main__
    if hasattr(__main__, "app") and __main__.app:
        print(f"🔍 Búsqueda semántica para: {seed[:50]}...")
        vector_results = __main__.app.vector_engine.search(seed, top_k=limit)
        for rel_path, score in vector_results:
            if score > 0.5: # Umbral de relevancia semántica
                p = WIKI_DIR / rel_path
                if p.exists() and p.stem not in seen:
                    results.append(f"### [Relación Semántica: {p.name}]\n{p.read_text(encoding='utf-8')[:3000]}")
                    seen.add(p.stem)

    # Fallback/Complemento: Búsqueda clásica por palabras clave
    keywords = [k.lower() for k in seed.split() if len(k) > 3]
    if len(results) < limit:
        for path in iter_wiki_pages():
            if path.stem in seen: continue
            content = path.read_text(encoding="utf-8").lower()
            if any(kw in content or kw in path.stem.lower() for kw in keywords):
                results.append(f"### [Relación Palabra Clave: {path.name}]\n{path.read_text(encoding='utf-8')[:2000]}")
                seen.add(path.stem)
                if len(results) >= limit: break

    return "\n\n".join(results)

# --- MANTENIMIENTO DE LA WIKI ---

def rebuild_index():
    sections = {name: [] for name in SECTION_ORDER}
    for path in iter_wiki_pages():
        content = path.read_text(encoding="utf-8")
        sections[bucket_for_path(path)].append(f"- [[{path.stem}]] — {extract_summary(content)}")

    lines = ["# Índice de la Wiki", "", "- [Radar](dashboard.md)", "- [Log](log.md)"]
    for bucket in SECTION_ORDER:
        if sections[bucket]:
            lines.append(f"\n## {bucket.title()}")
            lines.extend(sections[bucket])
    lines.append(f"\n---\n*Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    (WIKI_DIR / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

def rebuild_dashboard():
    counts = {b: len(list((WIKI_DIR / b).glob("*.md"))) if (WIKI_DIR / b).exists() else 0 for b in SECTION_ORDER}
    
    recent = []
    for path in sorted(iter_wiki_pages(), key=lambda p: p.stat().st_mtime, reverse=True)[:10]:
        recent.append(f"- [[{path.stem}]] — {path.parent.name}")

    active_hypotheses = []
    if (WIKI_DIR / "hipotesis").exists():
        for path in sorted((WIKI_DIR / "hipotesis").glob("*.md"))[:8]:
            meta = extract_metadata(path.read_text(encoding="utf-8"))
            active_hypotheses.append(f"- [[{path.stem}]] — status: {meta['status']}")

    lines = [
        "# Radar", "", "## Resumen",
        *[f"- {b.title()}: {counts.get(b, 0)}" for b in SECTION_ORDER if b != "dashboard"],
        "", "## Reciente"
    ]
    lines.extend(recent or ["- Sin actividad."])
    lines.append("\n## Hipótesis activas")
    lines.extend(active_hypotheses or ["- Sin hipótesis activas."])
    lines.append(f"\n---\n*Dashboard actualizado: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    (WIKI_DIR / "dashboard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

def refresh_compiled_views():
    rebuild_index()
    rebuild_dashboard()

def append_log_entry(kind: str, title: str, details: list[str]):
    log_path = WIKI_DIR / "log.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = [f"## [{timestamp}] {kind} | {title}"] + [f"- {d}" for d in details]
    with FILE_LOCK:
        with open(log_path, "a", encoding="utf-8") as h:
            h.write("\n" + "\n".join(entry) + "\n")

# --- OPERACIONES DE ARCHIVO Y LLM ---

def archive_source(text: str, file_path: str | None) -> Path:
    ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    if file_path:
        src = Path(file_path)
        target_dir = RAW_ASSETS_DIR if src.suffix.lower() in (".pdf", ".png", ".jpg", ".jpeg", ".webp") else RAW_SOURCES_DIR
        target = target_dir / f"{ts}-{src.name}"
        shutil.copy2(src, target)
        return target
    target = RAW_SOURCES_DIR / f"{ts}-nota.md"
    target.write_text(text.strip() + "\n", encoding="utf-8")
    return target

def call_lm_studio(messages: list, timeout: int = 180) -> str:
    payload = {"model": MODEL_NAME, "messages": messages, "temperature": 0.1, "max_tokens": 32000}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(LM_STUDIO_URL, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = json.loads(resp.read().decode())["choices"][0]["message"]["content"]
            return content
    except Exception as e:
        raise ConnectionError(f"Error conectando a LM Studio: {e}")

# --- CLASE PRINCIPAL UI ---

class WikiApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LLM Wiki - Brain Shell")
        self.geometry("1200x800")
        
        # Inicializar Motor Vectorial
        self.vector_engine = VectorEngine(WIKI_DIR)
        
        self._current_file = None
        self._setup_ui()
        self._refresh_tree()

    def _setup_ui(self):
        # Estilos
        style = ttk.Style()
        style.theme_use("clam")
        
        # Layout principal
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Sidebar (Treeview)
        sidebar = ttk.Frame(paned, width=250)
        paned.add(sidebar, weight=1)
        
        self.tree = ttk.Treeview(sidebar, show="tree")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Editor / Output Area
        main_area = ttk.Frame(paned)
        paned.add(main_area, weight=4)

        self.editor = scrolledtext.ScrolledText(main_area, wrap=tk.WORD, font=("Consolas", 11))
        self.editor.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Botonera
        btns = ttk.Frame(main_area)
        btns.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(btns, text="Nuevo Ingest", command=self._gui_ingest).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Preguntar a la Wiki", command=self._gui_query).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Guardar Cambios", command=self._gui_save_editor).pack(side=tk.LEFT, padx=2)
        self.btn_guardar_consulta = ttk.Button(btns, text="Guardar en Wiki", command=self._gui_archive_query, state=tk.DISABLED)
        self.btn_guardar_consulta.pack(side=tk.LEFT, padx=2)
        
        self.status = tk.StringVar(value="Listo")
        ttk.Label(self, textvariable=self.status, relief=tk.SUNKEN, anchor=tk.W).pack(fill=tk.X)

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        # Reconstruir árbol por carpetas
        for bucket in SECTION_ORDER:
            node = self.tree.insert("", "end", text=bucket.title(), open=(bucket=="dashboard"))
            path = WIKI_DIR / bucket
            if path.exists():
                for f in sorted(path.glob("*.md")):
                    self.tree.insert(node, "end", text=f.name, values=(str(f),))

    def _on_tree_select(self, event):
        sel = self.tree.selection()
        if not sel: return
        item = self.tree.item(sel[0])
        if item["values"]:
            path = Path(item["values"][0])
            self._open_file(path)

    def _open_file(self, path: Path):
        self._current_file = path
        content = path.read_text(encoding="utf-8")
        self.editor.delete("1.0", tk.END)
        self.editor.insert(tk.END, content)
        self.status.set(f"Editando: {path.name}")
        self.btn_guardar_consulta.config(state=tk.DISABLED)

    def _gui_save_editor(self):
        if not self._current_file: return
        content = self.editor.get("1.0", tk.END).strip()
        with FILE_LOCK:
            self._current_file.write_text(content, encoding="utf-8")
            # Actualizar vector
            self.vector_engine.update_page(wiki_relpath(self._current_file), content)
        self.status.set("Guardado exitosamente.")
        refresh_compiled_views()
        self._refresh_tree()

    def _gui_ingest(self):
        source = filedialog.askopenfilename(title="Seleccionar fuente")
        if not source: return
        
        self.status.set("Procesando ingesta semántica...")
        threading.Thread(target=self._proc_ingest, args=(source,), daemon=True).start()

    def _proc_ingest(self, source_path):
        try:
            path = Path(source_path)
            # Extraer contenido real (BUG-03 fix)
            ext = path.suffix.lower()
            if ext == ".pdf":
                from pdfminer.high_level import extract_text
                text = extract_text(str(path))
            elif ext in (".png", ".jpg", ".jpeg"):
                text = f"[Imagen: {path.name} procesada como asset]"
            else:
                text = path.read_text(encoding="utf-8")
            
            # Archivar original
            archived = archive_source(text, str(path))
            
            # Contexto semántico
            ctx = build_relevant_context(path.name + " " + text[:500], limit=10)
            
            messages = [
                {"role": "system", "content": load_schema()},
                {"role": "user", "content": f"Archivo: {path.name}\n\nContenido:\n{text}\n\nContexto Wiki:\n{ctx}"}
            ]
            
            raw = call_lm_studio(messages)
            res = parse_json_response(raw)
            
            # Guardar páginas y vectorizar
            saved_info = []
            for p in res.get("paginas", []):
                dest = APP_DIR / p["ruta"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(p["contenido"], encoding="utf-8")
                self.vector_engine.update_page(wiki_relpath(dest), p["contenido"])
                saved_info.append(dest.name)
            
            append_log_entry("ingest", path.name, [f"Creadas: {', '.join(saved_info)}"])
            refresh_compiled_views()
            self.after(0, lambda: [self._refresh_tree(), self.status.set("Ingesta completada.")])
            
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e)))

    def _gui_query(self):
        q = filedialog.askstring("Consulta Semántica", "Preguntale a tu wiki:")
        if not q: return
        self.status.set("Buscando en vectores y consultando LLM...")
        threading.Thread(target=self._proc_query, args=(q,), daemon=True).start()

    def _proc_query(self, query):
        try:
            ctx = build_relevant_context(query, limit=15)
            messages = [
                {"role": "system", "content": load_schema()},
                {"role": "user", "content": f"CONSULTA: {query}\n\nCONTEXTO SEMÁNTICO:\n{ctx}"}
            ]
            raw = call_lm_studio(messages)
            res = parse_json_response(raw)
            
            self._consulta_activa = res
            self.after(0, lambda: [
                self.editor.delete("1.0", tk.END),
                self.editor.insert(tk.END, res["respuesta"]),
                self.status.set("Respuesta generada."),
                self.btn_guardar_consulta.config(state=tk.NORMAL)
            ])
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e)))

    def _gui_archive_query(self):
        if not hasattr(self, "_consulta_activa"): return
        res = self._consulta_activa
        title = slugify(res.get("titulo_archivo", "consulta-" + datetime.now().strftime("%H%M")))
        path = WIKI_DIR / "consultas" / f"{title}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(res["respuesta"], encoding="utf-8")
        
        self.vector_engine.update_page(wiki_relpath(path), res["respuesta"])
        append_log_entry("query", title, ["Consulta semántica archivada"])
        refresh_compiled_views()
        self._refresh_tree()
        self.status.set(f"Archivado: {path.name}")
        self.btn_guardar_consulta.config(state=tk.DISABLED)

if __name__ == "__main__":
    app = WikiApp()
    app.mainloop()
