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

# Eliminamos las constantes fijas para usar dinámicas en load_schema
FILE_LOCK = threading.Lock()

SECTION_ORDER = [
    "dashboard",
    "fuentes",
    "senales",
    "claims",
    "narrativas",
    "hipotesis",
    "escenarios",
    "acciones",
    "temas",
    "entidades",
    "conceptos",
    "consultas",
    "templates",
    "otros",
]

DEFAULT_SCHEMA = """Sos un asistente especializado en mantener una wiki personal generalista orientada a inteligencia y acción.
La fecha de hoy es __TODAY__ (__TIME__ hs). Usá SIEMPRE esta fecha en logs, ingests y respuestas.
IMPORTANTE: Respondé DIRECTAMENTE con JSON válido. No uses bloques de razonamiento ni texto fuera del JSON.

Objetivo del sistema:
- juntar información relevante: noticias, ideas, rumores, tweets, documentos, capturas, PDFs
- separar señales, hechos, interpretación y ruido
- detectar patrones, tensiones, narrativas, hipótesis, escenarios y acciones posibles
- mantener trazabilidad: toda conclusión debe poder rastrearse a fuentes y claims

REGLA DE CONECTIVIDAD (CRÍTICA):
- Usá SIEMPRE wikilinks de Obsidian `[[nombre-de-archivo]]` para referenciar otras páginas.
- PROHIBIDO usar texto plano o rutas como `wiki/fuentes/archivo.md` fuera de los corchetes dobles.
- El nombre del archivo dentro de los corchetes NO debe llevar la extensión .md.
- Si citás una fuente en "Trazabilidad", debés poner: "Fuente: [[nombre-de-la-fuente-generada]]".

La wiki vive en archivos markdown organizados así:
  wiki/dashboard.md      — radar operativo actual
  wiki/fuentes/          — resumen estructurado de cada fuente
  wiki/senales/          — señales tempranas o fragmentarias
  wiki/claims/           — afirmaciones atómicas y trazables
  wiki/narrativas/       — marcos interpretativos en circulación
  wiki/hipotesis/        — tesis e hipótesis de trabajo
  wiki/escenarios/       — futuros plausibles y condiciones
  wiki/acciones/         — acciones o próximos pasos evaluables
  wiki/temas/            — dossiers o asuntos amplios
  wiki/entidades/        — personas, empresas, países, instituciones, protocolos
  wiki/conceptos/        — marcos, ideas, procesos y términos
  wiki/consultas/        — respuestas valiosas archivadas
  wiki/index.md          — índice general
  wiki/log.md            — log cronológico
  wiki/templates/        — plantillas de referencia
  raw/fuentes-originales — archivo inmutable de las fuentes
  raw/assets             — imágenes y binarios relacionados

- Reglas de integridad:
- Tratá `raw/` como archivo inmutable.
- Si una página ya existe (el sistema te proporcionará su contenido), NO LA SOBRESCRIBAS a ciegas. Debés INTEGRAR la información nueva, preservando los hallazgos valiosos anteriores.
- Usá [[wikilinks]] bidireccionales: si creás un "claim" desde una "fuente", asegurate de que la fuente también mencione al claim y viceversa.
- Combatí el crecimiento huérfano: buscá activamente temas o entidades existentes para conectar las nuevas notas.

## Al INGERIR una fuente
Devolvé SOLO un JSON con este formato:
{
  "operacion": "ingest",
  "paginas": [
    {"ruta": "wiki/fuentes/nombre.md", "contenido": "...markdown...", "confidence": 0.8},
    {"ruta": "wiki/senales/senal-2026-04-09-001.md", "contenido": "...markdown...", "confidence": 0.6},
    {"ruta": "wiki/claims/clm-2026-04-09-001.md", "contenido": "...markdown...", "confidence": 0.7},
    {"ruta": "wiki/hipotesis/tesis-ejemplo.md", "contenido": "...markdown...", "confidence": 0.6}
  ],
  "resumen": "Qué se procesó y por qué importa"
}

Reglas de ingest:
- No devuelvas `wiki/index.md`, `wiki/log.md` ni `wiki/dashboard.md`.
- Podés actualizar o crear páginas en todas las categorías.
- En la sección "Trazabilidad" o "Evidencia", usá EXCLUSIVAMENTE [[wikilinks]] a la página de la fuente o páginas relacionadas. NO USES TEXTO PLANO.
- Si una fuente es rumor o señal débil, preservá su valor potencial sin tratarla como hecho confirmado.

## Al RESPONDER una consulta
Devolvé SOLO un JSON:
{
  "operacion": "query",
  "respuesta": "Tu respuesta en markdown",
  "archivar": true,
  "titulo_archivo": "slug-descriptivo"
}

Reglas de query:
- Basate prioritariamente en la wiki compilada.
- Usá [[wikilinks]] para citar páginas de la wiki en tu respuesta.
- Respondé idealmente en bloques: hechos, contexto, interpretación, escenarios, acciones posibles.

## Al hacer LINT
Devolvé SOLO un JSON.
IMPORTANTE: En todas tus respuestas (Query, Ingest, Lint), cada vez que menciones una página, fuente o entidad en una lista O TABLA, debés usar obligatoriamente [[wikilinks]].

## Confidence Score (0.0 a 1.0)
- 0.9-1.0: fuente primaria o dato oficial verificable
- 0.7-0.8: medio conocido o evidencia fuerte pero indirecta
- 0.5-0.6: rumor, fuente secundaria o inferencia plausible
- 0.3-0.4: especulación débil o dato sin sustento

Marcá contenido débil (<0.6) con ⚠️.
"""

DEFAULT_DOCS = """# App Documentation

## Qué es
`wiki_app.py` es una app de escritorio en Python/Tkinter para construir una wiki personal generalista con ayuda de LM Studio.

La idea no es solo guardar información. La idea es transformar fuentes dispersas en:
- contexto útil
- señales legibles
- claims trazables
- narrativas, hipótesis y escenarios
- acciones mejor pensadas

## Objetivo del sistema
El sistema está pensado para:
- capturar información relevante
- separar señales, hechos, interpretaciones y rumores
- preservar trazabilidad
- detectar patrones, tensiones y temas emergentes
- construir narrativas, hipótesis, escenarios y acciones posibles

## Estructura del proyecto
```text
files/
  wiki_app.py
  wiki_schema.md
  APP_DOCUMENTATION.md
  raw/
    fuentes-originales/
    assets/
  wiki/
    dashboard.md
    index.md
    log.md
    fuentes/
    senales/
    claims/
    narrativas/
    hipotesis/
    escenarios/
    acciones/
    temas/
    entidades/
    conceptos/
    consultas/
    templates/
```

## Flujo de trabajo
1. Ingerís una fuente.
2. La app archiva el original en `raw/`.
3. El modelo propone páginas compiladas en la wiki.
4. La app guarda esas páginas.
5. La app recompone `index.md` y `dashboard.md`.
6. El log registra qué cambió.

## Tipos de páginas
### `fuentes/`
Resumen estructurado de cada input original.

### `senales/`
Indicios tempranos, débiles o ambiguos que todavía no alcanzan el nivel de claim.

### `claims/`
Afirmaciones atómicas y trazables.

### `narrativas/`
Marcos interpretativos en circulación.

### `hipotesis/`
Tesis de trabajo y explicaciones tentativas.

### `escenarios/`
Futuros plausibles, condiciones y consecuencias.

### `acciones/`
Qué mirar, validar, construir, evitar o ejecutar.

### `temas/`
Dossiers amplios donde convergen múltiples capas.

### `entidades/`
Personas, empresas, países, organismos, protocolos, etc.

### `conceptos/`
Marcos, ideas, procesos, doctrinas y términos.

### `consultas/`
Respuestas archivadas por la app cuando una consulta vale la pena conservar.

## Artefactos mantenidos por la app
### `index.md`
Índice navegable de todo el contenido compilado.

### `dashboard.md`
Radar operativo con conteos, páginas recientes e hipótesis visibles.

### `log.md`
Historial cronológico de ingestas, consultas archivadas y regeneraciones importantes.

## Cadena conceptual
`fuente -> señal -> claim -> narrativa/mapa -> hipótesis -> escenario -> acción`

## Criterios de calidad
- trazabilidad a fuentes
- separación entre hecho e interpretación
- soporte para señales débiles
- utilidad para decidir sin simplificar de más
- bajo sesgo de dominio

## Scores recomendados
- `reliability`
- `signal_strength`
- `impact`
- `actionability`

## Notas de implementación
- La app usa `urllib` para hablar con LM Studio.
- PDFs se extraen con `pdfminer.six` o `pdftotext`.
- Imágenes se envían como base64.
- El prompt principal vive en `wiki_schema.md`.

## Extensiones futuras recomendadas
- watchlists
- resúmenes diarios y semanales
- detección de convergencia entre fuentes
- score por relevancia personal
- score temporal o decadencia de señales
- búsqueda semántica o embeddings
"""

DEFAULT_ROOT_README = """# wiki-app

Repositorio público del proyecto `LLM Wiki`.

La app vive en [files/](./files) y está pensada para construir una wiki personal generalista orientada a inteligencia y acción usando LM Studio.

Documentación principal:
- [files/README.md](./files/README.md)
- [files/APP_DOCUMENTATION.md](./files/APP_DOCUMENTATION.md)
"""

TEMPLATE_CLAIM = """# Claim Template

---
type: claim
claim_id: clm-YYYY-MM-DD-001
claim_kind: hecho
claim_date: YYYY-MM-DD
entity:
topics: []
source_refs: []
confidence: 0.70
impact: medio
status: activo
---

## Claim
Escribí acá la afirmación atómica.

## Evidencia
- fuente 1

## Notas
- contexto
"""

TEMPLATE_SIGNAL = """# Signal Template

---
type: senal
signal_id: senal-YYYY-MM-DD-001
signal_date: YYYY-MM-DD
strength: debil
topics: []
entities: []
source_refs: []
status: abierta
---

## Señal

## Por qué importa

## Qué falta para elevarla
"""

TEMPLATE_HYPOTHESIS = """# Hypothesis Template

---
type: hipotesis
status: activa
priority: media
created_at: YYYY-MM-DD
updated_at: YYYY-MM-DD
topics: []
entities: []
time_horizon: medio
confidence: 0.60
---

## Hipótesis

## Qué la dispara

## Evidencia a favor

## Evidencia en contra

## Qué falta validar

## Escenarios

## Posibles acciones

## Riesgos

## Próxima revisión
"""

TEMPLATE_SCENARIO = """# Scenario Template

---
type: escenario
status: abierto
updated_at: YYYY-MM-DD
topics: []
entities: []
horizon: medio
---

## Escenario

## Condiciones

## Gatillos

## Consecuencias

## Qué cambiaría la lectura
"""

TEMPLATE_ACTION = """# Action Template

---
type: accion
status: pendiente
updated_at: YYYY-MM-DD
owner:
topics: []
entities: []
priority: media
---

## Acción

## Objetivo

## Basada en

## Próximo paso

## Riesgos
"""

BG = "#0d1117"
BG2 = "#161b22"
BG3 = "#21262d"
ACCENT = "#f0b429"
ACCENT2 = "#3fb950"
ACCENT3 = "#f85149"
ACCENT4 = "#a371f7"
FG = "#e6edf3"
FG2 = "#8b949e"
BORDER = "#30363d"
FONT_MONO = ("Courier New", 10)
FONT_UI = ("Segoe UI", 10)
FONT_BIG = ("Segoe UI", 13, "bold")
FONT_MED = ("Segoe UI", 11)
INGEST_FILE_TYPES = [
    ("Todos", "*.pdf *.png *.jpg *.jpeg *.txt *.md *.webp"),
    ("PDF", "*.pdf"),
    ("Imagen", "*.png *.jpg *.jpeg *.webp"),
    ("Texto", "*.txt *.md"),
]


def ensure_text_file(path: Path, content: str):
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def migrate_legacy_structure():
    legacy = WIKI_DIR / "oportunidades"
    target = WIKI_DIR / "hipotesis"
    if legacy.exists():
        target.mkdir(parents=True, exist_ok=True)
        for path in legacy.glob("*.md"):
            destination = target / path.name
            if not destination.exists():
                shutil.move(str(path), str(destination))


def ensure_dirs():
    for directory in [
        WIKI_DIR,
        RAW_DIR,
        RAW_SOURCES_DIR,
        RAW_ASSETS_DIR,
        WIKI_DIR / "fuentes",
        WIKI_DIR / "senales",
        WIKI_DIR / "claims",
        WIKI_DIR / "narrativas",
        WIKI_DIR / "hipotesis",
        WIKI_DIR / "escenarios",
        WIKI_DIR / "acciones",
        WIKI_DIR / "temas",
        WIKI_DIR / "entidades",
        WIKI_DIR / "conceptos",
        WIKI_DIR / "consultas",
        WIKI_DIR / "templates",
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    migrate_legacy_structure()
    ensure_text_file(WIKI_DIR / "index.md", "# Índice de la Wiki\n\n*Vacío — ingresá tu primera fuente.*\n")
    ensure_text_file(WIKI_DIR / "dashboard.md", "# Radar\n\n*Sin actividad todavía.*\n")
    ensure_text_file(WIKI_DIR / "log.md", "# Log de operaciones\n\n")
    ensure_text_file(SCHEMA_FILE, DEFAULT_SCHEMA)
    ensure_text_file(DOCS_FILE, DEFAULT_DOCS)
    ensure_text_file(ROOT_README, DEFAULT_ROOT_README)
    ensure_text_file(WIKI_DIR / "templates" / "claim-template.md", TEMPLATE_CLAIM)
    ensure_text_file(WIKI_DIR / "templates" / "signal-template.md", TEMPLATE_SIGNAL)
    ensure_text_file(WIKI_DIR / "templates" / "hypothesis-template.md", TEMPLATE_HYPOTHESIS)
    ensure_text_file(WIKI_DIR / "templates" / "scenario-template.md", TEMPLATE_SCENARIO)
    ensure_text_file(WIKI_DIR / "templates" / "action-template.md", TEMPLATE_ACTION)


def load_schema() -> str:
    hoy = datetime.now().strftime("%Y-%m-%d")
    hora = datetime.now().strftime("%H:%M")
    schema = SCHEMA_FILE.read_text(encoding="utf-8")
    return schema.replace("__TODAY__", hoy).replace("__TIME__", hora)


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


def extract_metadata(content: str) -> dict[str, str]:
    metadata = {"updated": "s/d", "confidence": "s/d", "status": "s/d", "type": "s/d"}
    in_frontmatter = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter and ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if key in {"updated_at", "signal_date", "claim_date", "created_at"} and metadata["updated"] == "s/d":
                metadata["updated"] = value
            elif key == "status":
                metadata["status"] = value
            elif key == "type":
                metadata["type"] = value
        if "Última actualización" in line:
            parts = [part.strip() for part in line.split("|") if part.strip()]
            if parts:
                metadata["updated"] = parts[-1]
        if "Confidence" in line:
            parts = [part.strip() for part in line.split("|") if part.strip()]
            if parts:
                metadata["confidence"] = parts[-1]
    return metadata


def iter_wiki_pages():
    for path in sorted(WIKI_DIR.rglob("*.md")):
        if path.name in ("index.md", "log.md", "dashboard.md"):
            continue
        yield path


def bucket_for_path(path: Path) -> str:
    name = path.parent.name
    return name if name in SECTION_ORDER else "otros"


def build_page_catalog() -> str:
    sections = {name: [] for name in SECTION_ORDER}
    for path in iter_wiki_pages():
        content = path.read_text(encoding="utf-8")
        meta = extract_metadata(content)
        sections[bucket_for_path(path)].append(
            f"- [[{path.stem}]] | {extract_title(path, content)} | {extract_summary(content)} | type: {meta['type']} | status: {meta['status']} | actualizado: {meta['updated']} | confidence: {meta['confidence']}"
        )
    lines = ["# Catálogo de la wiki"]
    for bucket in SECTION_ORDER:
        if sections[bucket]:
            lines.append(f"\n## {bucket.title()}")
            lines.extend(sections[bucket])
    return "\n".join(lines)


def read_wiki_context() -> str:
    parts = []
    for path in [WIKI_DIR / "dashboard.md", WIKI_DIR / "index.md", WIKI_DIR / "log.md"]:
        if path.exists():
            parts.append(f"### {wiki_relpath(path)}\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(parts)


def score_page(path: Path, content: str, query: str) -> int:
    terms = [term for term in re.findall(r"\w+", query.lower()) if len(term) > 2]
    haystack = f"{path.stem} {path.parent.name} {content[:5000]}".lower()
    score = 0
    for term in terms:
        score += haystack.count(term)
        if term in path.stem.lower():
            score += 3
    return score


def select_relevant_pages(query: str, limit: int = 10) -> list[Path]:
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


def build_relevant_context(query: str, limit: int = 10) -> str:
    pages = []
    for path in select_relevant_pages(query, limit=limit):
        pages.append(f"### {wiki_relpath(path)}\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(pages)


def rebuild_index():
    sections = {name: [] for name in SECTION_ORDER}
    for path in iter_wiki_pages():
        content = path.read_text(encoding="utf-8")
        rel = path.stem
        sections[bucket_for_path(path)].append(f"- [[{rel}]] — {extract_summary(content)}")

    lines = ["# Índice de la Wiki", "", "- [Radar](dashboard.md)", "- [Log](log.md)"]
    for bucket in SECTION_ORDER:
        if sections[bucket]:
            lines.append(f"\n## {bucket.title()}")
            lines.extend(sections[bucket])
    lines.append(f"\n---\n*Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    (WIKI_DIR / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def recent_pages(limit: int = 8) -> list[Path]:
    return sorted(iter_wiki_pages(), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]


def rebuild_dashboard():
    counts = {}
    for bucket in SECTION_ORDER:
        if bucket == "dashboard":
            continue
        directory = WIKI_DIR / bucket
        counts[bucket] = len(list(directory.glob("*.md"))) if directory.exists() else 0

    active_hypotheses = []
    for path in sorted((WIKI_DIR / "hipotesis").glob("*.md"))[:8]:
        content = path.read_text(encoding="utf-8")
        meta = extract_metadata(content)
        active_hypotheses.append(f"- [[{path.stem}]] — status: {meta['status']}")

    recent = []
    for path in recent_pages():
        content = path.read_text(encoding="utf-8")
        recent.append(f"- [[{path.stem}]] — {path.parent.name}")

    lines = [
        "# Radar",
        "",
        "## Resumen",
        f"- Fuentes: {counts.get('fuentes', 0)}",
        f"- Señales: {counts.get('senales', 0)}",
        f"- Claims: {counts.get('claims', 0)}",
        f"- Narrativas: {counts.get('narrativas', 0)}",
        f"- Hipótesis: {counts.get('hipotesis', 0)}",
        f"- Escenarios: {counts.get('escenarios', 0)}",
        f"- Acciones: {counts.get('acciones', 0)}",
        f"- Temas: {counts.get('temas', 0)}",
        f"- Entidades: {counts.get('entidades', 0)}",
        f"- Conceptos: {counts.get('conceptos', 0)}",
        f"- Consultas archivadas: {counts.get('consultas', 0)}",
        "",
        "## Reciente",
    ]
    lines.extend(recent or ["- Sin actividad todavía."])
    lines.append("")
    lines.append("## Hipótesis activas")
    lines.extend(active_hypotheses or ["- No hay hipótesis activas todavía."])
    lines.append(f"\n---\n*Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    (WIKI_DIR / "dashboard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_log_entry(kind: str, title: str, details: list[str]):
    log_path = WIKI_DIR / "log.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"## [{timestamp}] {kind} | {title}"]
    lines.extend(f"- {detail}" for detail in details)
    with FILE_LOCK:
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write("\n" + "\n".join(lines) + "\n")


def archive_source(text_content: str, file_path: str | None) -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    if file_path:
        src = Path(file_path)
        target_dir = RAW_ASSETS_DIR if src.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf") else RAW_SOURCES_DIR
        target = target_dir / f"{timestamp}-{src.name}"
        shutil.copy2(src, target)
        return target
    target = RAW_SOURCES_DIR / f"{timestamp}-nota.md"
    target.write_text(text_content.strip() + "\n", encoding="utf-8")
    return target


def confidence_badge(score: float) -> str:
    if score >= 0.9:
        return "🟢"
    if score >= 0.7:
        return "🟡"
    if score >= 0.5:
        return "🟠"
    return "🔴"


def normalize_route(path: Path) -> Path:
    resolved = path.resolve()
    try:
        if resolved.is_relative_to(WIKI_DIR) or resolved.is_relative_to(RAW_DIR):
            return resolved
    except AttributeError: # Compatibilidad con Python < 3.9
        str_resolved = str(resolved)
        if str_resolved.startswith(str(WIKI_DIR.resolve())) or str_resolved.startswith(str(RAW_DIR.resolve())):
            return resolved
    raise ValueError(f"Ruta fuera del proyecto: {path}")


def save_pages(pages: list[dict]) -> list[tuple[Path, float]]:
    saved = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with FILE_LOCK:
        for page in pages:
            path = normalize_route(APP_DIR / page["ruta"])
            path.parent.mkdir(parents=True, exist_ok=True)
            content = page["contenido"].strip()
            confidence = float(page.get("confidence", 0.7))
            
            # Si el archivo ya existe, guardamos un backup temporal antes de escribir
            # Esto es una red de seguridad extra
            if path.exists():
                backup = path.with_suffix(".md.bak")
                shutil.copy2(path, backup)
            
            footer = (
                f"\n\n---\n"
                f"| Campo | Valor |\n"
                f"|-------|-------|\n"
                f"| Última actualización | {timestamp} |\n"
                f"| Confidence | {confidence_badge(confidence)} {confidence:.0%} |\n"
            )
            if "última actualización" not in content.lower():
                content += footer
            path.write_text(content + "\n", encoding="utf-8")
            saved.append((path, confidence))
    return saved


def image_to_base64(path: str) -> tuple[str, str]:
    ext = Path(path).suffix.lower()
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(ext, "image/png")
    with open(path, "rb") as handle:
        return base64.b64encode(handle.read()).decode(), mime


def extract_pdf_text(path: str) -> str:
    try:
        from pdfminer.high_level import extract_text
        return extract_text(path)
    except ImportError:
        pass
    try:
        result = subprocess.run(["pdftotext", path, "-"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout
    except Exception:
        pass
    return f"[PDF: {Path(path).name} — instalá pdfminer.six o pdftotext para extraer texto]"


def list_orphans() -> list[str]:
    # Función rápida para dar al modelo una lista de objetivos a conectar
    all_pages = {p.stem for p in iter_wiki_pages()}
    referenced = set()
    for p in iter_wiki_pages():
        content = p.read_text(encoding="utf-8")
        links = re.findall(r"\[\[(.*?)\]\]", content)
        for link in links:
            referenced.add(link.split("|")[0].strip())
    return sorted(list(all_pages - referenced))


def build_ingest_messages(text_content: str, file_path: str | None = None) -> list[dict]:
    orphans = list_orphans()[:15] # Top 15 para no saturar
    context = build_relevant_context(text_content, limit=8)
    
    system_prompt = load_schema()
    if orphans:
        system_prompt += f"\n\nOBJETIVOS DE CONECTIVIDAD (Páginas huérfanas que necesitan links):\n- " + "\n- ".join([f"[[{o}]]" for o in orphans])
    
    user_prompt = f"/no_think\nIngerir esta fuente:\n\n{text_content}"
    if context:
        user_prompt += f"\n\n---\nContexto relevante de la wiki:\n{context}"
    
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]


def refresh_compiled_views():
    rebuild_index()
    rebuild_dashboard()


def build_ingest_messages(text_content: str, file_path: str | None, archived_source: Path) -> list[dict]:
    context = "\n\n".join(
        filter(
            None,
            [
                read_wiki_context(),
                build_page_catalog(),
                build_relevant_context(Path(file_path).name if file_path else text_content[:300], limit=12),
            ],
        )
    )
    messages = [{"role": "system", "content": load_schema()}]

    if file_path:
        ext = Path(file_path).suffix.lower()
        if ext == ".pdf":
            extracted = extract_pdf_text(file_path)
            user_content = (
                f"/no_think\nIngerí esta fuente PDF ({Path(file_path).name}). "
                f"La copia inmutable quedó archivada en `{wiki_relpath(archived_source)}`.\n\n"
                f"{extracted}\n\n---\nContexto actual de la wiki:\n{context}"
            )
            messages.append({"role": "user", "content": user_content})
        elif ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            b64, mime = image_to_base64(file_path)
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                        {
                            "type": "text",
                            "text": (
                                f"/no_think\nIngerí esta imagen ({Path(file_path).name}) en la wiki. "
                                f"La copia inmutable quedó archivada en `{wiki_relpath(archived_source)}`.\n\n"
                                f"Contexto actual:\n{context}"
                            ),
                        },
                    ],
                }
            )
        else:
            user_content = (
                f"/no_think\nIngerí esta fuente ({Path(file_path).name}). "
                f"La copia inmutable quedó archivada en `{wiki_relpath(archived_source)}`.\n\n"
                f"{Path(file_path).read_text(encoding='utf-8')}\n\n---\nContexto actual:\n{context}"
            )
            messages.append({"role": "user", "content": user_content})
    else:
        messages.append(
            {
                "role": "user",
                "content": (
                    f"/no_think\nIngerí esta fuente. "
                    f"La nota original quedó archivada en `{wiki_relpath(archived_source)}`.\n\n"
                    f"{text_content}\n\n---\nContexto actual de la wiki:\n{context}"
                ),
            }
        )
    return messages


def process_ingest_source(text_content: str, file_path: str | None = None, already_archived: Path | None = None) -> tuple[list[tuple[Path, float]], str, Path]:
    archived_source = already_archived if already_archived else archive_source(text_content, file_path)
    raw = call_lm_studio(build_ingest_messages(text_content, file_path, archived_source), timeout=180)
    result = parse_json_response(raw)
    saved = save_pages(result.get("paginas", []))
    refresh_compiled_views()
    append_log_entry(
        "ingest",
        archived_source.name,
        [f"Fuente archivada en: `{wiki_relpath(archived_source)}`"]
        + [f"Página actualizada: `{wiki_relpath(path)}` | confidence {score:.0%}" for path, score in saved],
    )
    refresh_compiled_views()
    return saved, result.get("resumen", "Procesado."), archived_source


def call_lm_studio(messages: list, timeout: int = 120) -> str:
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 32768,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        LM_STUDIO_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode())
            content = result["choices"][0]["message"]["content"]
            if result["choices"][0].get("finish_reason") == "length":
                print("⚠️ ATENCIÓN: LM Studio cortó la respuesta por límite de tokens.")
            return content
    except urllib.error.URLError as exc:
        raise ConnectionError(f"No se pudo conectar a LM Studio: {exc.reason}") from exc


def parse_json_response(raw: str) -> dict:
    raw = raw.strip()
    if "</think>" in raw:
        raw = raw[raw.rfind("</think>") + len("</think>"):]
    
    # Limpiar bloques de código markdown
    raw = re.sub(r"```(?:json)?\s*", "", raw)
    raw = re.sub(r"```", "", raw).strip()
    
    # Intentar encontrar el primer bloque de llaves balanceado
    start = raw.find("{")
    if start == -1:
        raise ValueError("No se encontró '{' en la respuesta")
        
    # Método simple de balanceo de llaves para no cortar JSONs anidados
    stack = 0
    end = -1
    for i in range(start, len(raw)):
        if raw[i] == "{":
            stack += 1
        elif raw[i] == "}":
            stack -= 1
            if stack == 0:
                end = i + 1
                break
                
    if end == -1:
        # Si falló el balanceo, intentar el método anterior como fallback
        end = raw.rfind("}") + 1
        
    if start == -1 or end <= start:
        raise ValueError("No se pudo extraer un JSON válido")
        
    return json.loads(raw[start:end])


class WikiApp(tk.Tk):
    def __init__(self):
        super().__init__()
        ensure_dirs()
        refresh_compiled_views()
        self.title("LLM Wiki  ·  LM Studio")
        self.geometry("1140x760")
        self.minsize(920, 620)
        self.configure(bg=BG)
        self._consulta_pendiente = None
        self._current_file = None
        self._build_ui()
        self._refresh_tree()

    def _build_ui(self):
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left = tk.Frame(self, bg=BG2, width=250)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_propagate(False)
        left.rowconfigure(3, weight=1)
        left.columnconfigure(0, weight=1)

        hdr = tk.Frame(left, bg=BG2, pady=16)
        hdr.grid(row=0, column=0, sticky="ew")
        tk.Label(hdr, text="LLM Wiki", font=FONT_BIG, bg=BG2, fg=ACCENT).pack()
        tk.Label(hdr, text="signals, narratives, hypotheses", font=("Segoe UI", 8), bg=BG2, fg=FG2).pack()

        tk.Frame(left, bg=BORDER, height=1).grid(row=1, column=0, sticky="ew")

        btns = tk.Frame(left, bg=BG2, pady=8, padx=12)
        btns.grid(row=2, column=0, sticky="ew")
        btns.columnconfigure(0, weight=1)

        def btn(text: str, cmd, color: str, row: int):
            button = tk.Button(
                btns,
                text=text,
                command=cmd,
                bg=color,
                fg=BG if color != BG3 else FG,
                font=("Segoe UI", 9, "bold"),
                relief="flat",
                cursor="hand2",
                activebackground=color,
                activeforeground=BG if color != BG3 else FG,
                padx=10,
                pady=7,
            )
            button.grid(row=row, column=0, sticky="ew", pady=3)

        btn("＋  Ingerir fuente", self._open_ingest, ACCENT, 0)
        btn("≣  Batch ingest", self._open_batch_ingest, "#2f81f7", 1)
        btn("🔍  Consultar wiki", self._open_query, "#388bfd", 2)
        btn("🛠  Lint (salud)", self._run_lint, BG3, 3)
        btn("📡  Ver radar", self._open_dashboard, BG3, 4)
        btn("⟳  Actualizar árbol", self._refresh_tree, BG3, 5)

        tree_frame = tk.Frame(left, bg=BG2)
        tree_frame.grid(row=3, column=0, sticky="nsew", padx=8, pady=4)
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Wiki.Treeview", background=BG2, foreground=FG, fieldbackground=BG2, borderwidth=0, rowheight=22, font=FONT_UI)
        style.configure("Wiki.Treeview.Heading", background=BG3, foreground=FG2, borderwidth=0)
        style.map("Wiki.Treeview", background=[("selected", BG3)], foreground=[("selected", ACCENT)])

        self.tree = ttk.Treeview(tree_frame, style="Wiki.Treeview", show="tree")
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        tk.Label(left, text="● LM Studio", font=("Segoe UI", 8), bg=BG2, fg=ACCENT2).grid(row=4, column=0, pady=6)

        right = tk.Frame(self, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        topbar = tk.Frame(right, bg=BG3, height=40)
        topbar.grid(row=0, column=0, sticky="ew")
        topbar.grid_propagate(False)
        topbar.columnconfigure(1, weight=1)

        self.page_title = tk.Label(topbar, text="Seleccioná un archivo", font=FONT_MED, bg=BG3, fg=FG2, padx=16)
        self.page_title.grid(row=0, column=0, sticky="w", pady=8)

        self.btn_guardar_consulta = tk.Button(
            topbar,
            text="💾  Guardar consulta",
            command=self._guardar_consulta_actual,
            bg=ACCENT4,
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            cursor="hand2",
            padx=10,
            pady=4,
        )
        
        self.btn_save_file = tk.Button(
            topbar,
            text="💾  Guardar cambios",
            command=self._save_current_file,
            bg=ACCENT2,
            fg=BG,
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            cursor="hand2",
            padx=10,
            pady=4,
        )

        tk.Label(topbar, text=f"modelo: {MODEL_NAME}", font=("Segoe UI", 8), bg=BG3, fg=FG2, padx=16).grid(row=0, column=2, sticky="e")

        editor_frame = tk.Frame(right, bg=BG)
        editor_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=8)
        editor_frame.rowconfigure(0, weight=1)
        editor_frame.columnconfigure(0, weight=1)

        self.editor = scrolledtext.ScrolledText(
            editor_frame,
            bg=BG2,
            fg=FG,
            insertbackground=ACCENT,
            font=FONT_MONO,
            relief="flat",
            borderwidth=0,
            wrap="word",
            padx=16,
            pady=12,
            selectbackground=BG3,
            selectforeground=ACCENT,
        )
        self.editor.grid(row=0, column=0, sticky="nsew")

        self.status = tk.Label(right, text="Listo.", font=("Segoe UI", 8), bg=BG3, fg=FG2, anchor="w", padx=12, pady=4)
        self.status.grid(row=2, column=0, sticky="ew")

    def _refresh_tree(self):
        refresh_compiled_views()
        self.tree.delete(*self.tree.get_children())

        def add_dir(parent, path: Path):
            for item in sorted(path.iterdir()):
                if item.name.startswith("."):
                    continue
                if item.is_dir():
                    node = self.tree.insert(parent, "end", text=f"📁 {item.name}", values=[str(item)])
                    add_dir(node, item)
                elif item.suffix == ".md":
                    self.tree.insert(parent, "end", text=f"📄 {item.name}", values=[str(item)])

        root = self.tree.insert("", "end", text="📂 wiki", values=[str(WIKI_DIR)], open=True)
        add_dir(root, WIKI_DIR)

    def _show_file(self, path: Path):
        self._current_file = path
        self.page_title.config(text=wiki_relpath(path))
        self.editor.config(state="normal")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", path.read_text(encoding="utf-8"))
        
    def _save_current_file(self):
        if not hasattr(self, "_current_file") or not self._current_file:
            return
        content = self.editor.get("1.0", "end-1c")
        self._current_file.write_text(content, encoding="utf-8")
        self._set_status(f"✅ Guardado: {self._current_file.name}", ACCENT2)
        refresh_compiled_views()

    def _on_tree_select(self, _event):
        selection = self.tree.selection()
        if not selection:
            return
        values = self.tree.item(selection[0], "values")
        if not values:
            return
        path = Path(values[0])
        if path.is_file():
            self.btn_guardar_consulta.grid_forget()
            self.btn_save_file.grid(row=0, column=1, sticky="e", padx=8, pady=6)
            self._show_file(path)

    def _open_dashboard(self):
        refresh_compiled_views()
        self._show_file(WIKI_DIR / "dashboard.md")

    def _open_ingest(self):
        win = tk.Toplevel(self)
        win.title("Ingerir fuente")
        win.geometry("640x520")
        win.configure(bg=BG)
        win.grab_set()

        tk.Label(win, text="Ingerir fuente nueva", font=FONT_BIG, bg=BG, fg=ACCENT).pack(pady=(20, 4))
        tk.Label(win, text="Pegá texto o seleccioná un archivo PDF, imagen o markdown", font=FONT_UI, bg=BG, fg=FG2).pack()

        txt = scrolledtext.ScrolledText(
            win,
            bg=BG2,
            fg=FG,
            font=FONT_MONO,
            relief="flat",
            borderwidth=1,
            insertbackground=ACCENT,
            height=14,
            padx=10,
            pady=8,
        )
        txt.pack(fill="both", expand=True, padx=20, pady=12)
        self._ingest_file_path = None

        def pick_file():
            file_path = filedialog.askopenfilename(
                filetypes=INGEST_FILE_TYPES
            )
            if file_path:
                self._ingest_file_path = file_path
                txt.delete("1.0", "end")
                txt.insert("1.0", f"[Archivo seleccionado: {file_path}]")

        btn_frame = tk.Frame(win, bg=BG)
        btn_frame.pack(fill="x", padx=20, pady=(0, 16))

        tk.Button(btn_frame, text="📂  Abrir archivo", command=pick_file, bg=BG3, fg=FG, font=FONT_UI, relief="flat", cursor="hand2", padx=12, pady=6).pack(side="left")

        def do_ingest():
            content = txt.get("1.0", "end").strip()
            if not content:
                messagebox.showwarning("Vacío", "Ingresá contenido o seleccioná un archivo.")
                return
            win.destroy()
            self._run_ingest(content, self._ingest_file_path)

        tk.Button(btn_frame, text="⚡  Procesar con LM Studio", command=do_ingest, bg=ACCENT, fg=BG, font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2", padx=16, pady=6).pack(side="right")

    def _open_batch_ingest(self):
        win = tk.Toplevel(self)
        win.title("Batch ingest")
        win.geometry("700x520")
        win.configure(bg=BG)
        win.grab_set()

        tk.Label(win, text="Batch ingest", font=FONT_BIG, bg=BG, fg=ACCENT).pack(pady=(20, 4))
        tk.Label(
            win,
            text="Seleccioná varios archivos o cargá todo `raw/fuentes-originales` uno por uno.",
            font=FONT_UI,
            bg=BG,
            fg=FG2,
        ).pack()

        preview = scrolledtext.ScrolledText(
            win,
            bg=BG2,
            fg=FG,
            font=FONT_MONO,
            relief="flat",
            borderwidth=1,
            height=16,
            padx=10,
            pady=8,
        )
        preview.pack(fill="both", expand=True, padx=20, pady=12)

        selected_files: list[str] = []

        def render_selection():
            preview.delete("1.0", "end")
            if not selected_files:
                preview.insert("1.0", "Sin archivos seleccionados.\n")
                return
            preview.insert("1.0", "\n".join(selected_files))

        def pick_files():
            files = filedialog.askopenfilenames(filetypes=INGEST_FILE_TYPES)
            if files:
                selected_files.clear()
                selected_files.extend(files)
                render_selection()

        def load_raw_folder():
            selected_files.clear()
            for path in sorted(RAW_SOURCES_DIR.glob("*")):
                if path.is_file():
                    selected_files.append(str(path))
            render_selection()

        def do_batch():
            if not selected_files:
                messagebox.showwarning("Vacío", "Seleccioná archivos o cargá la carpeta raw.")
                return
            win.destroy()
            self._run_batch_ingest(selected_files)

        btn_frame = tk.Frame(win, bg=BG)
        btn_frame.pack(fill="x", padx=20, pady=(0, 16))

        tk.Button(btn_frame, text="📂  Seleccionar archivos", command=pick_files, bg=BG3, fg=FG, font=FONT_UI, relief="flat", cursor="hand2", padx=12, pady=6).pack(side="left")
        tk.Button(btn_frame, text="📦  Cargar raw/", command=load_raw_folder, bg=BG3, fg=FG, font=FONT_UI, relief="flat", cursor="hand2", padx=12, pady=6).pack(side="left", padx=8)
        tk.Button(btn_frame, text="⚡  Procesar secuencialmente", command=do_batch, bg=ACCENT, fg=BG, font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2", padx=16, pady=6).pack(side="right")

        render_selection()

    def _run_ingest(self, text_content: str, file_path: str | None = None):
        self._set_status("⏳ Procesando con LM Studio...", FG2)

        def worker():
            try:
                saved, summary, _archived_source = process_ingest_source(text_content, file_path)
                
                # Eliminar archivo original tras éxito (comportamiento Inbox)
                if file_path:
                    try:
                        p = Path(file_path)
                        if p.exists():
                            p.unlink()
                    except Exception as e:
                        print(f"No se pudo eliminar el archivo original: {e}")
                
                self.after(0, lambda: self._ingest_done(saved, summary))
            except Exception as exc:
                self.after(0, lambda: self._set_status(f"❌ Error: {exc}", ACCENT3))

        threading.Thread(target=worker, daemon=True).start()

    def _run_batch_ingest(self, file_paths: list[str]):
        self._set_status(f"⏳ Batch ingest: 0/{len(file_paths)}", FG2)

        def worker():
            processed = 0
            created_pages = 0
            last_summary = ""
            
            # Detectar si estamos procesando la carpeta raw para evitar re-archivar
            paths_obj = [Path(p) for p in file_paths]
            is_raw_source = all(p.is_relative_to(RAW_DIR) for p in paths_obj if p.exists())

            for idx, file_path in enumerate(file_paths, start=1):
                try:
                    self.after(0, lambda i=idx, total=len(file_paths), name=Path(file_path).name: self._set_status(f"⏳ Batch ingest {i}/{total}: {name}", FG2))
                    
                    path_obj = Path(file_path)
                    if path_obj.suffix.lower() in (".txt", ".md"):
                        text_content = path_obj.read_text(encoding="utf-8")
                    else:
                        text_content = f"[Archivo seleccionado: {file_path}]"
                    
                    # Si ya está en raw, pasamos el path original para evitar duplicar
                    already_archived = path_obj if is_raw_source else None
                    saved, summary, _archived_source = process_ingest_source(text_content, file_path, already_archived=already_archived)
                    
                    processed += 1
                    created_pages += len(saved)
                    last_summary = summary
                    
                    # Eliminar archivo original tras éxito para mantener el "Inbox" limpio
                    try:
                        if path_obj.exists():
                            path_obj.unlink()
                    except Exception as e:
                        print(f"No se pudo eliminar {file_path}: {e}")
                except Exception as exc:
                    print(f"Error procesando {file_path}: {exc}")
                    # Continuamos con el siguiente archivo
                    continue

            self.after(0, lambda: self._batch_ingest_done(processed, len(file_paths), created_pages, last_summary))

        threading.Thread(target=worker, daemon=True).start()

    def _batch_ingest_done(self, processed: int, total: int, created_pages: int, summary: str):
        self._refresh_tree()
        self._set_status(f"✅ Batch ingest completo: {processed}/{total} archivos · {created_pages} páginas · {summary}", ACCENT2)
        self._show_file(WIKI_DIR / "dashboard.md")

    def _ingest_done(self, saved: list[tuple[Path, float]], summary: str):
        self._refresh_tree()
        if saved:
            scores = [score for _, score in saved]
            avg = sum(scores) / len(scores)
            self._set_status(f"✅ {summary}  ·  {len(saved)} páginas  ·  confianza promedio: {confidence_badge(avg)} {avg:.0%}", ACCENT2)
        else:
            self._set_status(f"✅ {summary}", ACCENT2)
        self._show_file(WIKI_DIR / "dashboard.md")

    def _open_query(self):
        win = tk.Toplevel(self)
        win.title("Consultar wiki")
        win.geometry("620x240")
        win.configure(bg=BG)
        win.grab_set()

        tk.Label(win, text="Consultar la wiki", font=FONT_BIG, bg=BG, fg="#388bfd").pack(pady=(20, 6))
        entry = tk.Entry(win, bg=BG2, fg=FG, font=FONT_MED, insertbackground=ACCENT, relief="flat", borderwidth=0)
        entry.pack(fill="x", padx=20, pady=6, ipady=10)
        entry.focus()

        def do_query(_event=None):
            question = entry.get().strip()
            if not question:
                return
            win.destroy()
            self._run_query(question)

        entry.bind("<Return>", do_query)
        tk.Button(win, text="Consultar →", command=do_query, bg="#388bfd", fg=BG, font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2", padx=16, pady=8).pack(pady=12)

    def _run_query(self, question: str):
        self._set_status("⏳ Consultando...", FG2)

        def worker():
            try:
                full_context = "\n\n".join(filter(None, [read_wiki_context(), build_page_catalog(), build_relevant_context(question, limit=12)]))
                messages = [
                    {"role": "system", "content": load_schema()},
                    {"role": "user", "content": f"/no_think\nPregunta: {question}\n\n---\nContenido de la wiki:\n{full_context}"},
                ]
                raw = call_lm_studio(messages, timeout=180)
                result = parse_json_response(raw)
                self.after(0, lambda: self._query_done(question, result.get("respuesta", raw), result.get("archivar", False), result.get("titulo_archivo", "")))
            except Exception as exc:
                self.after(0, lambda: self._set_status(f"❌ Error: {exc}", ACCENT3))

        threading.Thread(target=worker, daemon=True).start()

    def _query_done(self, question: str, response: str, archive: bool, title: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        content = f"# Consulta: {question}\n\n{response}\n\n---\n*{timestamp}*\n"
        self.editor.config(state="normal")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", content)
        self.page_title.config(text=f"Resultado: {question}")

        if archive and title:
            self._consulta_pendiente = (title, content, question)
            self.btn_save_file.grid_forget()
            self.btn_guardar_consulta.config(text="💾  Guardar en wiki")
            self.btn_guardar_consulta.grid(row=0, column=1, sticky="e", padx=8, pady=6)
            self._set_status("✅ Consulta completada  ·  El modelo sugiere archivar esta respuesta.", ACCENT4)
        else:
            self._consulta_pendiente = None
            self.btn_guardar_consulta.grid_forget()
            self._set_status("✅ Consulta completada.", ACCENT2)

    def _guardar_consulta_actual(self):
        if not self._consulta_pendiente:
            return
        try:
            title, content, question = self._consulta_pendiente
            path = WIKI_DIR / "consultas" / f"{slugify(title)[:60]}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            
            refresh_compiled_views()
            append_log_entry("consulta archivada", question, [f"Guardada en: `{wiki_relpath(path)}`"])
            
            self._consulta_pendiente = None
            if hasattr(self, "btn_guardar_consulta"):
                self.btn_guardar_consulta.grid_forget()
            
            self._refresh_tree()
            self._set_status(f"💾 Guardada en {wiki_relpath(path)}", ACCENT4)
            messagebox.showinfo("Éxito", f"Consulta archivada correctamente en:\n{wiki_relpath(path)}")
        except Exception as e:
            messagebox.showerror("Error al guardar", f"No se pudo guardar la consulta: {e}")

    def _run_lint(self):
        self._set_status("⏳ Analizando salud de la wiki...", FG2)

        def worker():
            try:
                lint_context = "\n\n".join(
                    filter(
                        None,
                        [
                            read_wiki_context(),
                            build_page_catalog(),
                            build_relevant_context("senales claims narrativas hipotesis escenarios acciones contradicciones huerfanas ruido tendencias temas", limit=14),
                        ],
                    )
                )
                messages = [
                    {"role": "system", "content": load_schema()},
                    {
                        "role": "user",
                        "content": (
                            "/no_think\nHacé un lint de la wiki. "
                            "Buscá contradicciones, páginas huérfanas, claims sin fecha o sin fuente, "
                            "hipotesis con evidencia débil, señales repetidas sin elevar, temas emergentes sin dossier y ruido repetido.\n\n"
                            f"{lint_context}"
                        ),
                    },
                ]
                raw = call_lm_studio(messages, timeout=180)
                result = parse_json_response(raw)
                self.after(0, lambda: self._lint_done(result.get("problemas", []), result.get("sugerencias", [])))
            except Exception as exc:
                self.after(0, lambda: self._set_status(f"❌ Error: {exc}", ACCENT3))

        threading.Thread(target=worker, daemon=True).start()

    def _lint_done(self, problems: list[str], suggestions: list[str]):
        self._set_status(f"✅ Lint: {len(problems)} problemas, {len(suggestions)} sugerencias.", ACCENT2)
        lines = ["# Reporte de Lint", ""]
        if problems:
            lines.append("## Problemas encontrados")
            lines.extend(f"- {problem}" for problem in problems)
        else:
            lines.append("## Sin problemas detectados")
        if suggestions:
            lines.append("")
            lines.append("## Sugerencias")
            lines.extend(f"- {suggestion}" for suggestion in suggestions)
        self.editor.config(state="normal")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", "\n".join(lines))
        self.page_title.config(text="Reporte de Lint")

    def _set_status(self, msg: str, color: str = FG2):
        self.status.config(text=msg, fg=color)
        self.update_idletasks()


if __name__ == "__main__":
    app = WikiApp()
    app.mainloop()
