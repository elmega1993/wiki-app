# LLM Wiki — App de escritorio

App de escritorio Python que conecta con LM Studio para construir
una wiki personal generalista de forma incremental.

Ahora sigue más de cerca el patrón de "LLM Wiki":
- `raw/` se usa como archivo inmutable de fuentes
- `wiki_schema.md` define el contrato y las convenciones de la wiki
- `index.md` y `log.md` los mantiene la app de forma determinista
- las consultas e ingestas usan contexto relevante en vez de cortar páginas por posición

## Requisitos

- Python 3.10+
- LM Studio corriendo en `http://localhost:1234`
- (Opcional) `pdfminer.six` para extraer texto de PDFs:
  ```
  pip install pdfminer.six
  ```

## Uso

```bash
python wiki_app.py
```

## Operaciones

| Botón | Qué hace |
|-------|----------|
| ＋ Ingerir fuente | Procesa texto, PDF o imagen y actualiza la wiki |
| 🔍 Consultar wiki | Hace una pregunta sobre el contenido acumulado |
| 🛠 Lint | Analiza la wiki buscando contradicciones y páginas huérfanas |
| ⟳ Actualizar árbol | Refresca el árbol de archivos del panel izquierdo |

## Estructura generada

```
wiki_schema.md   ← esquema/convenios que sigue el LLM
wiki/
  entidades/   ← personas, instituciones, empresas, países
  conceptos/   ← ideas, marcos, procesos
  temas/       ← dossiers amplios y cruces entre dominios
  fuentes/     ← resúmenes de cada fuente
  consultas/   ← respuestas valiosas archivadas
  index.md     ← índice general
  log.md       ← historial de operaciones
raw/           ← tus fuentes originales (inmutables, archivadas por la app)
```

## Configuración

Editá las primeras líneas de `wiki_app.py` para cambiar:
- `LM_STUDIO_URL` — si LM Studio corre en otra IP/puerto
- `MODEL_NAME`    — el modelo que tengas cargado
