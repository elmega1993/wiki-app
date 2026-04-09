#!/usr/bin/env python3
"""
LLM Wiki — App de escritorio
Conecta con LM Studio local para construir una wiki personal generalista.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import json
import os
import re
import base64
import shutil
from datetime import datetime
from pathlib import Path
import urllib.request
import urllib.error

# ── Configuración ──────────────────────────────────────────────────────────────
LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
MODEL_NAME     = "qwen/qwen3.5-9b"
APP_DIR        = Path(__file__).resolve().parent
WIKI_DIR       = APP_DIR / "wiki"
RAW_DIR        = APP_DIR / "raw"
SCHEMA_FILE    = APP_DIR / "wiki_schema.md"

_HOY  = datetime.now().strftime("%Y-%m-%d")
_HORA = datetime.now().strftime("%H:%M")

DEFAULT_SCHEMA = """Sos un asistente especializado en mantener una wiki personal generalista.
La fecha de hoy es __TODAY__ (__TIME__ hs). Usá SIEMPRE esta fecha en los logs, ingests y respuestas.
IMPORTANTE: Respondé DIRECTAMENTE con el JSON. NO uses bloques de razonamiento, NO escribas "Thinking Process", NO escribas explicaciones previas. Solo el JSON puro.
La wiki vive en archivos markdown organizados así:
  wiki/entidades/   — personas, organizaciones, países, empresas, instituciones
  wiki/conceptos/   — ideas, marcos, términos, procesos, doctrinas
  wiki/temas/       — asuntos o dossiers amplios con múltiples aristas
  wiki/fuentes/     — resúmenes de cada fuente ingerida
  wiki/index.md     — índice de todo el contenido
  wiki/log.md       — registro cronológico de operaciones

## Al INGERIR una fuente:
Devolvé SOLO un JSON con este formato exacto (sin markdown, sin texto extra):
{{
  "operacion": "ingest",
  "paginas": [
    {{{{"ruta": "wiki/fuentes/nombre.md", "contenido": "...markdown...", "confidence": 0.8}}}},
    {{{{"ruta": "wiki/entidades/empresa.md", "contenido": "...markdown...", "confidence": 0.9}}}}
  ],
  "resumen": "Breve descripción de lo que se procesó"
}}

## Al RESPONDER una consulta:
Devolvé SOLO un JSON:
{{
  "operacion": "query",
  "respuesta": "Tu respuesta en markdown",
  "archivar": true,
  "titulo_archivo": "slug-descriptivo-de-la-consulta"
}}

Regla: si la respuesta es valiosa (análisis, comparación, conclusión), poné "archivar": true y un título slug.
Si es solo una pregunta simple de dato, poné "archivar": false.

## Al hacer LINT:
Devolvé SOLO un JSON:
{{
  "operacion": "lint",
  "problemas": ["descripción de problema 1", "..."],
  "sugerencias": ["sugerencia 1", "..."]
}}

## Reglas de Confidence Score (0.0 a 1.0):
- 0.9-1.0: dato oficial, balance publicado, fuente primaria verificada
- 0.7-0.8: nota periodística de medio conocido, un solo artículo
- 0.5-0.6: rumor, fuente secundaria, inferencia
- 0.3-0.4: especulación, dato sin fuente clara
Cuando una misma entidad aparece en múltiples fuentes, el confidence sube.
Marcá claims de baja confianza (<0.6) con ⚠️ en el contenido markdown.

Reglas importantes:
- Marcá contradicciones con ⚠️
- Siempre actualizá wiki/index.md y wiki/log.md
- Usá fechas en formato YYYY-MM-DD
- Separá hechos observables de interpretación.
- No asumas que todo debe leerse en clave financiera: una fuente puede ser política, legal, geopolítica, tecnológica, cultural o mixta.
"""

# ── Colores / tema ─────────────────────────────────────────────────────────────
BG        = "#0d1117"
BG2       = "#161b22"
BG3       = "#21262d"
ACCENT    = "#f0b429"
ACCENT2   = "#3fb950"
ACCENT3   = "#f85149"
ACCENT4   = "#a371f7"   # violeta para consultas archivadas
FG        = "#e6edf3"
FG2       = "#8b949e"
BORDER    = "#30363d"
FONT_MONO = ("Courier New", 10)
FONT_UI   = ("Segoe UI", 10)
FONT_BIG  = ("Segoe UI", 13, "bold")
FONT_MED  = ("Segoe UI", 11)

# ── Utilidades de archivo ──────────────────────────────────────────────────────

def ensure_dirs():
    for d in [WIKI_DIR, RAW_DIR,
              WIKI_DIR/"entidades", WIKI_DIR/"conceptos", WIKI_DIR/"temas",
              WIKI_DIR/"fuentes",   WIKI_DIR/"consultas"]:
        d.mkdir(parents=True, exist_ok=True)
    if not (WIKI_DIR/"index.md").exists():
        (WIKI_DIR/"index.md").write_text("# Índice de la Wiki\n\n*Vacío — ingresá tu primera fuente.*\n")
    if not (WIKI_DIR/"log.md").exists():
        (WIKI_DIR/"log.md").write_text("# Log de operaciones\n\n")
    if not SCHEMA_FILE.exists():
        SCHEMA_FILE.write_text(DEFAULT_SCHEMA, encoding="utf-8")

def load_schema() -> str:
    schema = SCHEMA_FILE.read_text(encoding="utf-8")
    return schema.replace("__TODAY__", _HOY).replace("__TIME__", _HORA)

def slugify(text: str) -> str:
    text = re.sub(r"\s+", "-", text.strip().lower())
    text = re.sub(r"[^a-z0-9áéíóúñü\-_]+", "-", text, flags=re.IGNORECASE)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "sin-titulo"

def wiki_relpath(path: Path) -> str:
    return path.relative_to(APP_DIR).as_posix()

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

def extract_metadata(content: str) -> tuple[str, str]:
    updated = "s/d"
    confidence = "s/d"
    for line in content.splitlines():
        if "Última actualización" in line:
            parts = [part.strip() for part in line.split("|") if part.strip()]
            if parts:
                updated = parts[-1]
        if "Confidence" in line:
            parts = [part.strip() for part in line.split("|") if part.strip()]
            if parts:
                confidence = parts[-1]
    return updated, confidence

def iter_wiki_pages():
    for path in sorted(WIKI_DIR.rglob("*.md")):
        if path.name in ("index.md", "log.md"):
            continue
        yield path

def build_page_catalog() -> str:
    sections = {"entidades": [], "conceptos": [], "temas": [], "fuentes": [], "consultas": [], "otros": []}
    for path in iter_wiki_pages():
        content = path.read_text(encoding="utf-8")
        title = extract_title(path, content)
        summary = extract_summary(content)
        updated, confidence = extract_metadata(content)
        bucket = path.parent.name if path.parent.name in sections else "otros"
        sections[bucket].append(
            f"- `{wiki_relpath(path)}` | {title} | {summary} | actualizado: {updated} | confidence: {confidence}"
        )
    lines = ["# Catálogo de la wiki"]
    for bucket, items in sections.items():
        if items:
            lines.append(f"\n## {bucket.title()}")
            lines.extend(items)
    return "\n".join(lines)

def read_wiki_context():
    parts = []
    for f in [WIKI_DIR/"index.md", WIKI_DIR/"log.md"]:
        if f.exists():
            parts.append(f"### {wiki_relpath(f)}\n{f.read_text(encoding='utf-8')}")
    return "\n\n".join(parts)

def score_page(path: Path, content: str, query: str) -> int:
    terms = [term for term in re.findall(r"\w+", query.lower()) if len(term) > 2]
    haystack = f"{path.stem} {path.parent.name} {content[:4000]}".lower()
    score = 0
    for term in terms:
        score += haystack.count(term)
        if term in path.stem.lower():
            score += 3
    return score

def select_relevant_pages(query: str, limit: int = 8) -> list[Path]:
    if not query.strip():
        return list(iter_wiki_pages())[:limit]
    ranked = []
    for path in iter_wiki_pages():
        content = path.read_text(encoding="utf-8")
        score = score_page(path, content, query)
        if score > 0:
            ranked.append((score, path))
    ranked.sort(key=lambda item: (-item[0], str(item[1])))
    return [path for _, path in ranked[:limit]]

def build_relevant_context(query: str, limit: int = 8) -> str:
    pages = []
    for path in select_relevant_pages(query, limit=limit):
        pages.append(f"### {wiki_relpath(path)}\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(pages)

def rebuild_index():
    sections = {"entidades": [], "conceptos": [], "temas": [], "fuentes": [], "consultas": [], "otros": []}
    for path in iter_wiki_pages():
        content = path.read_text(encoding="utf-8")
        title = extract_title(path, content)
        summary = extract_summary(content)
        bucket = path.parent.name if path.parent.name in sections else "otros"
        rel = path.relative_to(WIKI_DIR).as_posix()
        sections[bucket].append(f"- [{title}]({rel}) — {summary}")

    lines = ["# Índice de la Wiki"]
    for bucket, items in sections.items():
        if items:
            lines.append(f"\n## {bucket.title()}")
            lines.extend(items)
    lines.append(f"\n---\n*Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    (WIKI_DIR / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

def append_log_entry(kind: str, title: str, details: list[str]):
    log_path = WIKI_DIR / "log.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"## [{timestamp}] {kind} | {title}"]
    lines.extend(f"- {detail}" for detail in details)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n" + "\n".join(lines) + "\n")

def archive_source(text_content: str, file_path: str | None) -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    if file_path:
        src = Path(file_path)
        target = RAW_DIR / f"{timestamp}-{src.name}"
        shutil.copy2(src, target)
        return target

    target = RAW_DIR / f"{timestamp}-nota.md"
    target.write_text(text_content.strip() + "\n", encoding="utf-8")
    return target

def confidence_badge(score: float) -> str:
    """Devuelve un badge de texto para el confidence score."""
    if score >= 0.9: return "🟢"
    if score >= 0.7: return "🟡"
    if score >= 0.5: return "🟠"
    return "🔴"

def save_pages(pages: list) -> list:
    saved = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    for p in pages:
        path     = APP_DIR / p["ruta"]
        path.parent.mkdir(parents=True, exist_ok=True)
        contenido  = p["contenido"]
        confidence = p.get("confidence", 0.7)
        badge      = confidence_badge(confidence)

        # Agregar bloque de metadata al pie
        footer = (
            f"\n\n---\n"
            f"| Campo | Valor |\n"
            f"|-------|-------|\n"
            f"| Última actualización | {timestamp} |\n"
            f"| Confidence | {badge} {confidence:.0%} |\n"
        )
        if "última actualización" not in contenido.lower():
            contenido += footer

        path.write_text(contenido, encoding="utf-8")
        saved.append((path, confidence))
    return saved

def image_to_base64(path: str) -> tuple:
    ext  = Path(path).suffix.lower()
    mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png",  ".gif": "image/gif",
            ".webp": "image/webp"}.get(ext, "image/png")
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode(), mime

def extract_pdf_text(path: str) -> str:
    try:
        from pdfminer.high_level import extract_text
        return extract_text(path)
    except ImportError:
        pass
    try:
        import subprocess
        r = subprocess.run(["pdftotext", path, "-"], capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout
    except Exception:
        pass
    return f"[PDF: {Path(path).name} — instalá pdfminer.six: pip install pdfminer.six]"

# ── Llamada al modelo ──────────────────────────────────────────────────────────

def call_lm_studio(messages: list, timeout: int = 120) -> str:
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 32768,
    }
    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        LM_STUDIO_URL, data=data,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode())
            return result["choices"][0]["message"]["content"]
    except urllib.error.URLError as e:
        raise ConnectionError(f"No se pudo conectar a LM Studio: {e.reason}")

def parse_json_response(raw: str) -> dict:
    raw = raw.strip()
    # Qwen thinking mode: descartar todo antes de </think>
    if "</think>" in raw:
        raw = raw[raw.rfind("</think>") + len("</think>"):]
    # Quitar bloques ```json ... ```
    raw = re.sub(r"```(?:json)?\s*", "", raw)
    raw = re.sub(r"```", "", raw)
    raw = raw.strip()
    # Buscar el ÚLTIMO bloque JSON completo (más confiable)
    start = raw.rfind("\n{")
    if start == -1:
        start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No se encontró JSON en la respuesta")
    return json.loads(raw[start:end])

# ── App principal ──────────────────────────────────────────────────────────────

class WikiApp(tk.Tk):
    def __init__(self):
        super().__init__()
        ensure_dirs()
        self.title("LLM Wiki  ·  LM Studio")
        self.geometry("1100x720")
        self.minsize(900, 600)
        self.configure(bg=BG)
        self._build_ui()
        self._refresh_tree()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # ── Panel izquierdo ──
        left = tk.Frame(self, bg=BG2, width=240)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_propagate(False)
        left.rowconfigure(3, weight=1)
        left.columnconfigure(0, weight=1)

        hdr = tk.Frame(left, bg=BG2, pady=16)
        hdr.grid(row=0, column=0, sticky="ew")
        tk.Label(hdr, text="LLM Wiki", font=FONT_BIG,
                 bg=BG2, fg=ACCENT).pack()
        tk.Label(hdr, text="powered by LM Studio", font=("Segoe UI", 8),
                 bg=BG2, fg=FG2).pack()

        tk.Frame(left, bg=BORDER, height=1).grid(row=1, column=0, sticky="ew")

        btns = tk.Frame(left, bg=BG2, pady=8, padx=12)
        btns.grid(row=2, column=0, sticky="ew")
        btns.columnconfigure(0, weight=1)

        def btn(text, cmd, color, row):
            b = tk.Button(btns, text=text, command=cmd,
                          bg=color, fg=BG if color != BG3 else FG,
                          font=("Segoe UI", 9, "bold"),
                          relief="flat", cursor="hand2",
                          activebackground=color,
                          activeforeground=BG if color != BG3 else FG,
                          padx=10, pady=7)
            b.grid(row=row, column=0, sticky="ew", pady=3)

        btn("＋  Ingerir fuente",  self._open_ingest,  ACCENT,   0)
        btn("🔍  Consultar wiki",   self._open_query,   "#388bfd", 1)
        btn("🛠  Lint (salud)",     self._run_lint,     BG3,      2)
        btn("⟳  Actualizar árbol", self._refresh_tree, BG3,      3)

        # Árbol
        tree_frame = tk.Frame(left, bg=BG2)
        tree_frame.grid(row=3, column=0, sticky="nsew", padx=8, pady=4)
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Wiki.Treeview",
                         background=BG2, foreground=FG, fieldbackground=BG2,
                         borderwidth=0, rowheight=22, font=FONT_UI)
        style.configure("Wiki.Treeview.Heading",
                         background=BG3, foreground=FG2, borderwidth=0)
        style.map("Wiki.Treeview",
                  background=[("selected", BG3)],
                  foreground=[("selected", ACCENT)])

        self.tree = ttk.Treeview(tree_frame, style="Wiki.Treeview", show="tree")
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        tk.Label(left, text="● LM Studio", font=("Segoe UI", 8),
                 bg=BG2, fg=ACCENT2).grid(row=4, column=0, pady=6)

        # ── Panel derecho ──
        right = tk.Frame(self, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        topbar = tk.Frame(right, bg=BG3, height=40)
        topbar.grid(row=0, column=0, sticky="ew")
        topbar.grid_propagate(False)
        topbar.columnconfigure(1, weight=1)

        self.page_title = tk.Label(topbar, text="Seleccioná un archivo",
                                   font=FONT_MED, bg=BG3, fg=FG2, padx=16)
        self.page_title.grid(row=0, column=0, sticky="w", pady=8)

        # Botón guardar consulta (oculto por defecto)
        self.btn_guardar = tk.Button(
            topbar, text="💾  Guardar consulta",
            command=self._guardar_consulta_actual,
            bg=ACCENT4, fg="white", font=("Segoe UI", 9, "bold"),
            relief="flat", cursor="hand2", padx=10, pady=4
        )
        # No se muestra hasta que haya una consulta archivable

        tk.Label(topbar, text=f"modelo: {MODEL_NAME}",
                 font=("Segoe UI", 8), bg=BG3, fg=FG2, padx=16
                 ).grid(row=0, column=2, sticky="e")

        editor_frame = tk.Frame(right, bg=BG)
        editor_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=8)
        editor_frame.rowconfigure(0, weight=1)
        editor_frame.columnconfigure(0, weight=1)

        self.editor = scrolledtext.ScrolledText(
            editor_frame,
            bg=BG2, fg=FG, insertbackground=ACCENT,
            font=FONT_MONO, relief="flat", borderwidth=0,
            wrap="word", padx=16, pady=12,
            selectbackground=BG3, selectforeground=ACCENT
        )
        self.editor.grid(row=0, column=0, sticky="nsew")

        self.status = tk.Label(right, text="Listo.",
                               font=("Segoe UI", 8), bg=BG3, fg=FG2,
                               anchor="w", padx=12, pady=4)
        self.status.grid(row=2, column=0, sticky="ew")

        # Estado interno para consulta archivable
        self._consulta_pendiente = None  # (titulo, contenido)

    # ── Árbol ─────────────────────────────────────────────────────────────────

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())

        def add_dir(parent, path: Path):
            for item in sorted(path.iterdir()):
                if item.name.startswith("."):
                    continue
                if item.is_dir():
                    node = self.tree.insert(parent, "end",
                                            text=f"📁 {item.name}",
                                            values=[str(item)])
                    add_dir(node, item)
                elif item.suffix == ".md":
                    self.tree.insert(parent, "end",
                                     text=f"📄 {item.name}",
                                     values=[str(item)])

        if WIKI_DIR.exists():
            root = self.tree.insert("", "end", text="📂 wiki",
                                    values=[str(WIKI_DIR)], open=True)
            add_dir(root, WIKI_DIR)

    def _on_tree_select(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        if not vals:
            return
        path = Path(vals[0])
        if path.is_file():
            self.page_title.config(text=wiki_relpath(path))
            self.editor.config(state="normal")
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", path.read_text(encoding="utf-8"))
            self._consulta_pendiente = None
            self.btn_guardar.grid_forget()

    # ── Ingerir ───────────────────────────────────────────────────────────────

    def _open_ingest(self):
        win = tk.Toplevel(self)
        win.title("Ingerir fuente")
        win.geometry("620x500")
        win.configure(bg=BG)
        win.grab_set()

        tk.Label(win, text="Ingerir fuente nueva", font=FONT_BIG,
                 bg=BG, fg=ACCENT).pack(pady=(20, 4))
        tk.Label(win, text="Pegá texto, o seleccioná un archivo PDF/imagen",
                 font=FONT_UI, bg=BG, fg=FG2).pack()

        txt = scrolledtext.ScrolledText(win, bg=BG2, fg=FG, font=FONT_MONO,
                                         relief="flat", borderwidth=1,
                                         insertbackground=ACCENT,
                                         height=14, padx=10, pady=8)
        txt.pack(fill="both", expand=True, padx=20, pady=12)

        self._ingest_file_path = None

        def pick_file():
            fp = filedialog.askopenfilename(
                filetypes=[("Todos", "*.pdf *.png *.jpg *.jpeg *.txt *.md"),
                           ("PDF", "*.pdf"), ("Imagen", "*.png *.jpg *.jpeg"),
                           ("Texto", "*.txt *.md")])
            if fp:
                self._ingest_file_path = fp
                txt.delete("1.0", "end")
                txt.insert("1.0", f"[Archivo seleccionado: {fp}]")

        btn_frame = tk.Frame(win, bg=BG)
        btn_frame.pack(fill="x", padx=20, pady=(0, 16))

        tk.Button(btn_frame, text="📂  Abrir archivo",
                  command=pick_file,
                  bg=BG3, fg=FG, font=FONT_UI, relief="flat",
                  cursor="hand2", padx=12, pady=6).pack(side="left")

        def do_ingest():
            content = txt.get("1.0", "end").strip()
            if not content:
                messagebox.showwarning("Vacío", "Ingresá contenido o seleccioná un archivo.")
                return
            win.destroy()
            self._run_ingest(content, self._ingest_file_path)

        tk.Button(btn_frame, text="⚡  Procesar con LM Studio",
                  command=do_ingest,
                  bg=ACCENT, fg=BG, font=("Segoe UI", 10, "bold"),
                  relief="flat", cursor="hand2", padx=16, pady=6).pack(side="right")

    def _run_ingest(self, text_content: str, file_path=None):
        self._set_status("⏳ Procesando con LM Studio...", FG2)

        def worker():
            try:
                archived_source = archive_source(text_content, file_path)
                context = "\n\n".join(filter(None, [
                    read_wiki_context(),
                    build_page_catalog(),
                    build_relevant_context(Path(file_path).name if file_path else text_content[:300], limit=10),
                ]))
                messages = [{"role": "system", "content": load_schema()}]

                if file_path:
                    ext = Path(file_path).suffix.lower()
                    if ext == ".pdf":
                        extracted    = extract_pdf_text(file_path)
                        user_content = (
                            f"/no_think\nIngerí esta fuente PDF ({Path(file_path).name}). "
                            f"La copia inmutable quedó archivada en `{wiki_relpath(archived_source)}`.\n\n"
                            f"{extracted}\n\n---\nContexto actual de la wiki:\n{context}"
                        )
                        messages.append({"role": "user", "content": user_content})
                    elif ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
                        b64, mime = image_to_base64(file_path)
                        messages.append({
                            "role": "user",
                            "content": [
                                {"type": "image_url",
                                 "image_url": {"url": f"data:{mime};base64,{b64}"}},
                                {"type": "text",
                                 "text": (
                            f"/no_think\nIngerí esta imagen ({Path(file_path).name}) en la wiki. "
                                     f"La copia inmutable quedó archivada en `{wiki_relpath(archived_source)}`.\n\n"
                                     f"Contexto actual:\n{context}"
                                 )}
                            ]
                        })
                    else:
                        user_content = (
                            f"/no_think\nIngerí esta fuente ({Path(file_path).name}). "
                            f"La copia inmutable quedó archivada en `{wiki_relpath(archived_source)}`.\n\n"
                            f"{Path(file_path).read_text(encoding='utf-8')}\n\n---\nContexto actual:\n{context}"
                        )
                        messages.append({"role": "user", "content": user_content})
                else:
                    user_content = (
                        f"/no_think\nIngerí esta fuente. "
                        f"La nota original quedó archivada en `{wiki_relpath(archived_source)}`.\n\n"
                        f"{text_content}\n\n---\nContexto actual de la wiki:\n{context}"
                    )
                    messages.append({"role": "user", "content": user_content})

                raw    = call_lm_studio(messages)
                result = parse_json_response(raw)
                pages  = result.get("paginas", [])
                saved  = save_pages(pages)
                rebuild_index()
                append_log_entry(
                    "ingest",
                    archived_source.name,
                    [f"Fuente archivada en: `{wiki_relpath(archived_source)}`"]
                    + [f"Página actualizada: `{wiki_relpath(path)}` | confidence {score:.0%}" for path, score in saved]
                )
                resumen = result.get("resumen", "Procesado.")

                self.after(0, lambda: self._ingest_done(saved, resumen))

            except Exception as e:
                self.after(0, lambda: self._set_status(f"❌ Error: {e}", ACCENT3))

        threading.Thread(target=worker, daemon=True).start()

    def _ingest_done(self, saved, resumen):
        self._refresh_tree()
        # Mostrar confidence summary
        if saved:
            scores = [s for _, s in saved]
            avg    = sum(scores) / len(scores)
            badge  = confidence_badge(avg)
            self._set_status(
                f"✅ {resumen}  ·  {len(saved)} páginas  ·  confianza promedio: {badge} {avg:.0%}",
                ACCENT2
            )
        else:
            self._set_status(f"✅ {resumen}", ACCENT2)

        idx = WIKI_DIR / "index.md"
        if idx.exists():
            self.editor.config(state="normal")
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", idx.read_text(encoding="utf-8"))
            self.page_title.config(text=wiki_relpath(idx))

    # ── Query ─────────────────────────────────────────────────────────────────

    def _open_query(self):
        win = tk.Toplevel(self)
        win.title("Consultar wiki")
        win.geometry("580x220")
        win.configure(bg=BG)
        win.grab_set()

        tk.Label(win, text="Consultar la wiki", font=FONT_BIG,
                 bg=BG, fg="#388bfd").pack(pady=(20, 6))

        entry = tk.Entry(win, bg=BG2, fg=FG, font=FONT_MED,
                         insertbackground=ACCENT, relief="flat", borderwidth=0)
        entry.pack(fill="x", padx=20, pady=6, ipady=10)
        entry.focus()

        def do_query(e=None):
            q = entry.get().strip()
            if not q:
                return
            win.destroy()
            self._run_query(q)

        entry.bind("<Return>", do_query)

        tk.Button(win, text="Consultar →",
                  command=do_query,
                  bg="#388bfd", fg=BG, font=("Segoe UI", 10, "bold"),
                  relief="flat", cursor="hand2", padx=16, pady=8).pack(pady=12)

    def _run_query(self, question: str):
        self._set_status("⏳ Consultando...", FG2)

        def worker():
            try:
                full_context = "\n\n".join(filter(None, [
                    read_wiki_context(),
                    build_page_catalog(),
                    build_relevant_context(question, limit=10),
                ]))

                messages = [
                    {"role": "system", "content": load_schema()},
                    {"role": "user", "content": f"/no_think\nPregunta: {question}\n\n---\nContenido de la wiki:\n{full_context}"}
                ]
                raw      = call_lm_studio(messages, timeout=180)
                result   = parse_json_response(raw)
                respuesta = result.get("respuesta", raw)
                archivar  = result.get("archivar", False)
                titulo    = result.get("titulo_archivo", "")

                self.after(0, lambda: self._query_done(question, respuesta, archivar, titulo))

            except Exception as e:
                self.after(0, lambda: self._set_status(f"❌ Error: {e}", ACCENT3))

        threading.Thread(target=worker, daemon=True).start()

    def _query_done(self, question: str, respuesta: str, archivar: bool, titulo: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        contenido = f"# Consulta: {question}\n\n{respuesta}\n\n---\n*{timestamp}*\n"

        self.editor.config(state="normal")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", contenido)
        self.page_title.config(text=f"Resultado: {question}")

        if archivar and titulo:
            self._consulta_pendiente = (titulo, contenido, question)
            self.btn_guardar.config(text=f"💾  Guardar en wiki")
            self.btn_guardar.grid(row=0, column=1, sticky="e", padx=8, pady=6)
            self._set_status("✅ Consulta completada  ·  El modelo sugiere archivar esta respuesta.", ACCENT4)
        else:
            self._consulta_pendiente = None
            self.btn_guardar.grid_forget()
            self._set_status("✅ Consulta completada.", ACCENT2)

    def _guardar_consulta_actual(self):
        if not self._consulta_pendiente:
            return
        titulo, contenido, question = self._consulta_pendiente

        # Guardar en wiki/consultas/
        slug = re.sub(r"[^\w\-]", "-", titulo.lower())[:60]
        path = WIKI_DIR / "consultas" / f"{slug}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contenido, encoding="utf-8")

        rebuild_index()
        append_log_entry(
            "consulta archivada",
            question,
            [f"Guardada en: `{wiki_relpath(path)}`"]
        )

        self._consulta_pendiente = None
        self.btn_guardar.grid_forget()
        self._refresh_tree()
        self._set_status(f"💾 Guardada en {wiki_relpath(path)}", ACCENT4)

    # ── Lint ──────────────────────────────────────────────────────────────────

    def _run_lint(self):
        self._set_status("⏳ Analizando salud de la wiki...", FG2)

        def worker():
            try:
                lint_context = "\n\n".join(filter(None, [
                    read_wiki_context(),
                    build_page_catalog(),
                    build_relevant_context("contradicciones huerfanas confidence fechas fuentes", limit=12),
                ]))

                messages = [
                    {"role": "system", "content": load_schema()},
                    {"role": "user", "content": (
                        f"/no_think\nHacé un lint de la wiki. "
                        f"Buscá: contradicciones, páginas huérfanas, claims sin fecha, "
                        f"claims de baja confianza que necesiten corroboración, "
                        f"y sugerí qué fuentes investigar.\n\n"
                        f"{lint_context}"
                    )}
                ]
                raw    = call_lm_studio(messages, timeout=180)
                result = parse_json_response(raw)
                self.after(0, lambda: self._lint_done(
                    result.get("problemas",   []),
                    result.get("sugerencias", [])
                ))

            except Exception as e:
                self.after(0, lambda: self._set_status(f"❌ Error: {e}", ACCENT3))

        threading.Thread(target=worker, daemon=True).start()

    def _lint_done(self, problemas, sugerencias):
        self._set_status(
            f"✅ Lint: {len(problemas)} problemas, {len(sugerencias)} sugerencias.", ACCENT2
        )
        lines = ["# Reporte de Lint\n"]
        if problemas:
            lines.append("## ⚠️ Problemas encontrados")
            for p in problemas:
                lines.append(f"- {p}")
        else:
            lines.append("## ✅ Sin problemas detectados")
        if sugerencias:
            lines.append("\n## 💡 Sugerencias")
            for s in sugerencias:
                lines.append(f"- {s}")
        self.editor.config(state="normal")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", "\n".join(lines))
        self.page_title.config(text="Reporte de Lint")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_status(self, msg: str, color=FG2):
        self.status.config(text=msg, fg=color)
        self.update_idletasks()


# ── Entrada ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = WikiApp()
    app.mainloop()
