# Auditoría Completa: `wiki_app.py` (LLM Wiki)
> Basada en el patrón de Karpathy — [gist.github.com/karpathy/442a6bf555914893e9891c11519de94f](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)  
> Fecha de auditoría: 2026-04-10  
> Archivos analizados: `wiki_app.py`, `wiki_schema.md`, `migrate_corpus.py`, `wiki/` (contenido real)

---

## Resumen ejecutivo

El proyecto es sólido conceptualmente: la arquitectura de capas (raw → wiki → schema) está bien implementada, el sistema de tipos (fuentes/señales/claims/hipótesis/escenarios/acciones) es coherente y el uso de Obsidian como visor es acertado. Sin embargo se detectaron **2 bugs críticos que pueden causar pérdida de datos**, **1 bug que inutiliza una función entera en silencio**, **1 divergencia de schema que degrada la calidad del LLM** y varios problemas de calidad menores. A continuación el detalle completo.

---

## 🔴 Bugs Críticos (pérdida de datos / comportamiento roto)

### BUG-01 — Función `build_ingest_messages` duplicada: la primera versión es letra muerta

**Ubicación:** `wiki_app.py` líneas 786 y 809

```python
# Línea 786 — PRIMERA DEFINICIÓN (nunca se ejecuta)
def build_ingest_messages(text_content: str, file_path: str | None = None) -> list[dict]:
    orphans = list_orphans()[:15]
    context = build_relevant_context(text_content, limit=8)
    ...

# Línea 809 — SEGUNDA DEFINICIÓN (sobreescribe a la primera en Python)
def build_ingest_messages(text_content: str, file_path: str | None, archived_source: Path) -> list[dict]:
    context = "..."
    ...
```

En Python, definir dos funciones con el mismo nombre hace que la segunda reemplace a la primera. La primera versión (que incluye detección de páginas huérfanas y su inyección en el system prompt para forzar conectividad) **nunca se ejecuta**. El feature de conectividad activa está completamente inactivo.

**Fix:**

```python
# Eliminar la primera definición (líneas 786-807) y mover la lógica de orphans
# a la segunda definición:
def build_ingest_messages(text_content: str, file_path: str | None, archived_source: Path) -> list[dict]:
    orphans = list_orphans()[:15]
    system_prompt = load_schema()
    if orphans:
        system_prompt += "\n\nOBJETIVOS DE CONECTIVIDAD (Páginas huérfanas):\n- " + "\n- ".join(f"[[{o}]]" for o in orphans)
    
    context = "\n\n".join(filter(None, [
        read_wiki_context(),
        build_page_catalog(),
        build_relevant_context(Path(file_path).name if file_path else text_content[:300], limit=12),
    ]))
    messages = [{"role": "system", "content": system_prompt}]
    # ... resto del código de la segunda definición
```

---

### BUG-02 — El ingest individual elimina el archivo original del usuario

**Ubicación:** `wiki_app.py` líneas 1265–1275 (`_run_ingest`)

```python
def worker():
    try:
        saved, summary, _archived_source = process_ingest_source(text_content, file_path)
        
        # ⚠️ ESTO BORRA EL ARCHIVO ORIGINAL DEL USUARIO
        if file_path:
            try:
                p = Path(file_path)
                if p.exists():
                    p.unlink()  # ← DESTRUCCIÓN SILENCIOSA
```

El comportamiento "Inbox" (eliminar después de archivar) no está documentado en la UI, no pide confirmación al usuario, y el archivo original ya fue copiado a `raw/assets/` (binarios) o `raw/fuentes-originales/` (texto). Si la copia falló parcialmente, el original ya fue destruido. El mismo problema existe en `_run_batch_ingest` (línea 1314).

**Fix:**

```python
# Opción A: Eliminar el unlink completamente (Karpathy recomienda raw/ inmutable, no eliminación del original)
# Opción B: Preguntar al usuario
if file_path:
    if messagebox.askyesno("Eliminar original", 
                           f"¿Eliminar el archivo original?\n{file_path}\n\nYa fue archivado en raw/"):
        Path(file_path).unlink(missing_ok=True)
```

---

### BUG-03 — Batch ingest de imágenes y PDFs desde `raw/` envía texto placeholder al LLM

**Ubicación:** `wiki_app.py` líneas 1297–1302

```python
if path_obj.suffix.lower() in (".txt", ".md"):
    text_content = path_obj.read_text(encoding="utf-8")
else:
    text_content = f"[Archivo seleccionado: {file_path}]"  # ← PLACEHOLDER, NO CONTENIDO
```

Cuando se procesa batch desde `raw/fuentes-originales/`, los PDFs e imágenes envían el string literal `"[Archivo seleccionado: /ruta/archivo.pdf]"` al LLM. El modelo recibe basura en lugar del contenido real. `process_ingest_source` sí tiene lógica de extracción de PDF e imagen, pero depende de que `text_content` sea el contenido real O que `file_path` sea pasado correctamente — y acá solo se pasa el placeholder.

**Fix:**

```python
# En _run_batch_ingest, pasar siempre file_path y dejar que process_ingest_source
# maneje la extracción según extensión:
text_content = ""  # vacío, la extracción la hace process_ingest_source
if path_obj.suffix.lower() in (".txt", ".md"):
    text_content = path_obj.read_text(encoding="utf-8")
# Para PDF e imagen: pasar file_path, process_ingest_source los extrae internamente
saved, summary, _archived_source = process_ingest_source(
    text_content, str(path_obj), already_archived=already_archived
)
```

---

## 🟠 Bugs Importantes (degradan funcionalidad)

### BUG-04 — `refresh_compiled_views()` se llama dos veces seguidas en `process_ingest_source`

**Ubicación:** `wiki_app.py` líneas 876 y 883

```python
def process_ingest_source(...):
    ...
    saved = save_pages(result.get("paginas", []))
    refresh_compiled_views()       # ← Primera llamada
    append_log_entry(...)
    refresh_compiled_views()       # ← Segunda llamada idéntica e inmediata
    return saved, ...
```

Doble trabajo innecesario en cada ingest. Además `_run_ingest` llama a `self._refresh_tree()` (que internamente llama a `refresh_compiled_views()` nuevamente), resultando en hasta 3 rebuilds por operación.

**Fix:** Eliminar la primera llamada a `refresh_compiled_views()` en `process_ingest_source`.

---

### BUG-05 — Archivos `.md.bak` se acumulan silenciosamente en disco

**Ubicación:** `wiki_app.py` líneas 727–730 (`save_pages`)

```python
if path.exists():
    backup = path.with_suffix(".md.bak")
    shutil.copy2(path, backup)
# El backup nunca se elimina
```

Cada vez que se actualiza una página, se genera un `.md.bak`. Con uso intensivo esto produce decenas o cientos de backups que nunca se limpian. Obsidian los mostrará si no están filtrados.

**Fix:**

```python
# Opción A: eliminar el backup después de escritura exitosa
path.write_text(content + "\n", encoding="utf-8")
if backup.exists():
    backup.unlink()

# Opción B: si se quiere historial, mover a una carpeta .backups/ o usar git
```

---

### BUG-06 — `_ingest_file_path` es estado de instancia compartido entre ventanas

**Ubicación:** `wiki_app.py` línea 1165

```python
def _open_ingest(self):
    ...
    self._ingest_file_path = None   # Se resetea al ABRIR la ventana

    def pick_file():
        self._ingest_file_path = file_path  # Guarda en la instancia

    def do_ingest():
        self._run_ingest(content, self._ingest_file_path)  # Usa el de la instancia
```

Si el usuario abre dos ventanas de ingest o si hay algún race condition en el threading, `self._ingest_file_path` puede corresponder a un archivo de una sesión anterior. Debería ser una variable local del closure.

**Fix:**

```python
def _open_ingest(self):
    ingest_file_path = [None]  # Lista mutable para closure

    def pick_file():
        ...
        ingest_file_path[0] = file_path

    def do_ingest():
        self._run_ingest(content, ingest_file_path[0])
```

---

## 🟡 Divergencias de Schema y Configuración

### SCHEMA-01 — `wiki_schema.md` en disco no incluye las reglas críticas de wikilinks

**Problema:** `DEFAULT_SCHEMA` (hardcodeado en el código) contiene la `REGLA DE CONECTIVIDAD` con instrucciones detalladas de wikilinks bidireccionales, prohibición de rutas planas, y reglas de trazabilidad. `wiki_schema.md` en disco **no tiene ninguna de esas reglas**:

```bash
# Resultado:
grep "REGLA DE CONECTIVIDAD" wiki_schema.md  → 0 ocurrencias
grep "REGLA DE CONECTIVIDAD" wiki_app.py     → 1 ocurrencia (en DEFAULT_SCHEMA)
```

Como `load_schema()` lee `wiki_schema.md`, el LLM no recibe las reglas de conectividad. El archivo en disco es el que importa en producción, y está desactualizado respecto al código.

**Fix:** Actualizar `wiki_schema.md` para incluir toda la sección `REGLA DE CONECTIVIDAD`:

```markdown
## REGLA DE CONECTIVIDAD (CRÍTICA)
- Usá SIEMPRE wikilinks de Obsidian `[[nombre-de-archivo]]` para referenciar otras páginas.
- PROHIBIDO usar texto plano o rutas como `wiki/fuentes/archivo.md` fuera de los corchetes dobles.
- El nombre del archivo dentro de los corchetes NO debe llevar la extensión .md.
- Si citás una fuente en "Trazabilidad", debés poner: "Fuente: [[nombre-de-la-fuente-generada]]".
```

Y agregar un test al startup para verificar que `wiki_schema.md` contiene las secciones clave.

---

### SCHEMA-02 — El schema no instruye al LLM sobre el confidence badge

`wiki_schema.md` define el Confidence Score (0.0–1.0) pero no incluye las instrucciones del `confidence_badge` (🟢🟡🟠🔴) que sí están en `DEFAULT_SCHEMA`. El LLM no sabe que debe usar los emojis para marcar contenido débil.

---

## 🟡 Problemas de Calidad de Código

### QC-01 — Nombres de archivo con encoding roto en `wiki/senales/`

Tres archivos tienen nombres con `#U00f1` (representación incorrecta de `ñ`):

```
wiki/senales/se#U00f1al-anthropic-rails-nativos.md
wiki/senales/se#U00f1al-gobierno-deterioro-mayo-2026.md
wiki/senales/se#U00f1al-segundo-cerebro-llm.md
```

Esto puede causar problemas de navegación en Obsidian y en Windows (NTFS). El origen es que `slugify()` no normaliza bien la `ñ` en todos los sistemas operativos.

**Fix en `slugify()`:**

```python
import unicodedata

def slugify(text: str) -> str:
    # Normalizar Unicode antes de procesar
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")  # Elimina no-ASCII
    text = re.sub(r"\s+", "-", text.strip().lower())
    text = re.sub(r"[^a-z0-9\-_]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "sin-titulo"
```

Y renombrar los archivos existentes afectados.

---

### QC-02 — `extract_metadata()` rompe con `---` dentro del cuerpo del documento

```python
in_frontmatter = False
for line in content.splitlines():
    if stripped == "---":
        in_frontmatter = not in_frontmatter  # ← Toggle, no solo apertura/cierre
```

Si el contenido markdown tiene una línea `---` (separador horizontal), el parser entrará en modo frontmatter incorrectamente.

**Fix:**

```python
in_frontmatter = False
frontmatter_done = False
for line in content.splitlines():
    if stripped == "---":
        if not in_frontmatter and not frontmatter_done:
            in_frontmatter = True
        elif in_frontmatter:
            in_frontmatter = False
            frontmatter_done = True
        continue
    if in_frontmatter and ":" in stripped:
        ...
```

---

### QC-03 — `parse_json_response()`: el balanceo de llaves falla con strings que contienen `{` o `}`

```python
for i in range(start, len(raw)):
    if raw[i] == "{":
        stack += 1
    elif raw[i] == "}":
        stack -= 1
```

Si el contenido markdown dentro del JSON tiene `{variable}` o `{código}`, el contador se desbalanceará y se cortará el JSON prematuramente.

**Fix:** Usar `json.JSONDecoder().raw_decode()` que es robusto:

```python
def parse_json_response(raw: str) -> dict:
    raw = raw.strip()
    if "</think>" in raw:
        raw = raw[raw.rfind("</think>") + len("</think>"):]
    raw = re.sub(r"```(?:json)?\s*", "", raw)
    raw = re.sub(r"```", "", raw).strip()
    
    start = raw.find("{")
    if start == -1:
        raise ValueError("No se encontró '{' en la respuesta")
    
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(raw, start)  # Maneja strings con {} correctamente
    return obj
```

---

### QC-04 — Contexto duplicado en `_run_query`

```python
full_context = "\n\n".join(filter(None, [
    read_wiki_context(),          # dashboard + index + log
    build_page_catalog(),         # TODAS las páginas con resumen
    build_relevant_context(question, limit=12)  # Páginas más relevantes (también las lee completas)
]))
```

`build_page_catalog()` ya incluye un resumen de cada página. `build_relevant_context()` incluye las páginas completas. Las páginas más relevantes aparecen resumidas en el catálogo Y completas en el contexto relevante. Para wikis grandes esto puede saturar el contexto del LLM.

**Mejora sugerida:** En queries, optar por catálogo compacto + páginas relevantes completas, sin el catálogo completo. O limitar el catálogo a los primeros 300 chars por página.

---

### QC-05 — `score_page()` solo analiza los primeros 5000 caracteres

```python
haystack = f"{path.stem} {path.parent.name} {content[:5000]}".lower()
```

Páginas de hipótesis o escenarios extensas pueden tener la información relevante pasados los 5000 caracteres y quedar mal rankeadas.

---

### QC-06 — `call_lm_studio()` no tiene retry logic

Si LM Studio está cargando el modelo o experimenta un spike de carga, la request falla sin reintentos. Un timeout de 180 segundos sin retry es frágil.

**Mejora sugerida:**

```python
def call_lm_studio(messages: list, timeout: int = 120, retries: int = 2) -> str:
    last_exc = None
    for attempt in range(retries + 1):
        try:
            ...
            return content
        except urllib.error.URLError as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(2 ** attempt)  # Backoff exponencial
    raise ConnectionError(f"No se pudo conectar a LM Studio después de {retries+1} intentos: {last_exc.reason}")
```

---

### QC-07 — `migrate_corpus.py` solo migra `wiki/fuentes/`, no otras categorías

```python
for source_path in sorted((wiki_app.WIKI_DIR / "fuentes").glob("*.md")):
```

Si hay páginas en `senales/`, `claims/` o `hipotesis/` que necesitan migración al esquema nuevo, el script las ignora silenciosamente.

---

### QC-08 — `normalize_route()` fallback para Python < 3.9 tiene falso positivo potencial

```python
str_resolved = str(resolved)
if str_resolved.startswith(str(WIKI_DIR.resolve())) or str_resolved.startswith(str(RAW_DIR.resolve())):
```

Si `WIKI_DIR` fuera `/home/user/wiki` y existiera `/home/user/wiki-backup/`, un path en el backup pasaría la validación. Usar `os.path.commonpath()` es más robusto.

---

## 🟢 Mejoras Arquitecturales Sugeridas (no son bugs)

### MEJORA-01 — Agregar `wip.md` para continuidad entre sesiones

Comentado en los forks del gist original (glaucobrito): sin un archivo `wip.md`, cada sesión parte de cero. Un archivo con trabajo en progreso, preguntas abiertas y próximos pasos mejora drásticamente la continuidad.

### MEJORA-02 — Decadencia temporal de señales

Las señales (`senales/`) no tienen mecanismo de expiración. Una señal de hace 3 meses que nunca se elevó a claim o hipótesis ocupa espacio en el contexto y ruido en el lint. Agregar `expires_at` al frontmatter de señales y filtrar en `iter_wiki_pages()`.

### MEJORA-03 — Agregar `approved.json` / `rejected.json` para feedback loop

Otro patrón del gist de glaucobrito: registrar qué hipótesis o acciones fueron aceptadas o rechazadas permite que el LLM aprenda del historial de decisiones del usuario.

### MEJORA-04 — Separar schema para ingest, query y lint en secciones

El schema actual le pasa al modelo las instrucciones de los 3 modos aunque solo use uno. Esto infla el system prompt innecesariamente. Mejor construir el system prompt dinámicamente según la operación.

### MEJORA-05 — Exponere `MODEL_NAME` como configurable en la UI

Actualmente `MODEL_NAME = "qwen/qwen3.5-9b"` está hardcodeado. Un dropdown o campo de texto en la UI permitiría cambiar de modelo sin editar el código.

### MEJORA-06 — Agregar `search` (BM25 o similar) para wikis grandes

Karpathy menciona `qmd` explícitamente. Con más de ~100 páginas, el `select_relevant_pages()` actual (que solo hace keyword matching sin TF-IDF) pierde relevancia. Integrar `rank_bm25` de Python es trivial y mejora mucho la recuperación.

---

## Resumen de issues por severidad

| ID | Severidad | Tipo | Descripción |
|----|-----------|------|-------------|
| BUG-01 | 🔴 Crítico | Bug | Función `build_ingest_messages` duplicada — conectividad inactiva |
| BUG-02 | 🔴 Crítico | Bug | Eliminación silenciosa del archivo original del usuario |
| BUG-03 | 🔴 Crítico | Bug | Batch ingest de PDFs/imágenes envía placeholder al LLM |
| BUG-04 | 🟠 Importante | Bug | `refresh_compiled_views()` llamada doble en cada ingest |
| BUG-05 | 🟠 Importante | Bug | Archivos `.md.bak` acumulándose sin limpieza |
| BUG-06 | 🟠 Importante | Bug | `_ingest_file_path` como estado compartido de instancia |
| SCHEMA-01 | 🟠 Importante | Config | `wiki_schema.md` en disco no tiene reglas de wikilinks |
| SCHEMA-02 | 🟡 Moderado | Config | Schema sin instrucciones de confidence badge |
| QC-01 | 🟠 Importante | Calidad | Nombres de archivo con encoding roto (`#U00f1`) |
| QC-02 | 🟡 Moderado | Calidad | `extract_metadata()` rompe con `---` en cuerpo |
| QC-03 | 🟡 Moderado | Calidad | `parse_json_response()` falla con `{}` dentro de strings |
| QC-04 | 🟡 Moderado | Calidad | Contexto duplicado en queries |
| QC-05 | 🟡 Moderado | Calidad | Scoring solo sobre primeros 5000 chars |
| QC-06 | 🟡 Moderado | Calidad | Sin retry logic en `call_lm_studio()` |
| QC-07 | 🟡 Moderado | Calidad | `migrate_corpus.py` solo migra `fuentes/` |
| QC-08 | 🟢 Menor | Calidad | Falso positivo potencial en `normalize_route()` fallback |

---

## Orden de prioridad para fixes

1. **BUG-01** — La función duplicada anula el feature de conectividad. Fix rápido, alto impacto.
2. **SCHEMA-01** — Actualizar `wiki_schema.md` para incluir las reglas de wikilinks. Sin esto el LLM trabaja degradado.
3. **BUG-02** — Agregar confirmación antes de eliminar archivos originales. Alto riesgo de pérdida de datos del usuario.
4. **BUG-03** — Arreglar el batch ingest para PDFs e imágenes desde `raw/`.
5. **QC-01** — Renombrar los 3 archivos con encoding roto y parchear `slugify()`.
6. **BUG-04 + BUG-05** — Limpieza de doble refresh y backups.
7. **QC-02 + QC-03** — Robustez del parseo de metadata y JSON.

---

*Auditoría generada con Claude Sonnet 4.6 — 2026-04-10*
