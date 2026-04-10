# App Documentation

## Overview
`wiki_app.py` es una app de escritorio en Python/Tkinter para construir una wiki personal generalista usando LM Studio.

La app está pensada para convertir información dispersa en una base útil para pensar, construir, decidir e invertir mejor, sin reducir todo a “oportunidades”.

## Product Goal
La wiki no es solo un archivo de notas. Es un sistema para:
- capturar información relevante
- separar señales, hechos, interpretaciones y rumores
- preservar trazabilidad
- detectar patrones, tensiones y temas emergentes
- construir narrativas, hipótesis, escenarios y acciones posibles

## Inputs Esperados
- noticias
- tweets
- ideas propias
- rumores
- capturas de pantalla
- PDFs
- documentos

## Core Folders
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

## Folder Roles
### `raw/fuentes-originales/`
Archivo inmutable de textos y fuentes originales.

### `raw/assets/`
Imágenes, PDFs y binarios relacionados.

### `wiki/fuentes/`
Resumen estructurado de cada fuente ingresada.

### `wiki/senales/`
Indicios tempranos, débiles o ambiguos que todavía no son hechos consolidados.

### `wiki/claims/`
Afirmaciones atómicas y trazables.

### `wiki/narrativas/`
Marcos interpretativos en circulación.

### `wiki/hipotesis/`
Tesis de trabajo y explicaciones tentativas.

### `wiki/escenarios/`
Futuros plausibles, condiciones y consecuencias.

### `wiki/acciones/`
Qué mirar, validar, construir, evitar o ejecutar.

### `wiki/temas/`
Dossiers amplios sobre un asunto.

### `wiki/entidades/`
Personas, organizaciones, instituciones, países, activos, protocolos, etc.

### `wiki/conceptos/`
Marcos, doctrinas, procesos, términos, narrativas conceptuales.

### `wiki/consultas/`
Respuestas reutilizables archivadas desde la UI.

### `wiki/templates/`
Plantillas de referencia para señales, claims, hipótesis, escenarios y acciones.

## App-Managed Files
### `wiki/index.md`
Índice general generado por la app.

### `wiki/dashboard.md`
Radar operativo del estado actual de la wiki:
- conteos
- páginas recientes
- hipótesis activas

### `wiki/log.md`
Historial cronológico de ingestas y consultas archivadas.

## Main Workflows
### Ingest
1. El usuario pega texto o elige un archivo.
2. La app archiva la fuente original en `raw/`.
3. La app arma contexto con:
   - radar
   - index
   - log
   - catálogo de páginas
   - páginas relevantes
4. LM Studio devuelve páginas compiladas.
5. La app las guarda y recompone radar e índice.

### Query
1. El usuario pregunta.
2. La app selecciona contexto relevante.
3. LM Studio responde en markdown.
4. Si la respuesta vale la pena, se puede archivar en `wiki/consultas/`.

### Lint
El modelo analiza:
- contradicciones
- orfandad
- claims débiles
- hipótesis sin evidencia suficiente
- señales repetidas sin elevar
- temas emergentes sin dossier

## Conceptual Chain
`fuente -> señal -> claim -> narrativa/mapa -> hipótesis -> escenario -> acción`

## Why This Structure
Esto evita dos problemas comunes:
- guardar texto sin utilidad posterior
- mezclar rumores con hechos sin marcar diferencias

## Suggested Evaluation Axes
- `reliability`
- `signal_strength`
- `impact`
- `actionability`

## Technical Notes
- UI: Tkinter
- HTTP a LM Studio: `urllib`
- PDFs: `pdfminer.six` o `pdftotext`
- Imágenes: base64 inline
- Schema/prompt central: `wiki_schema.md`

## Next Recommended Upgrades
- watchlists por entidad o tema
- resúmenes diarios y semanales
- detección de convergencia entre fuentes
- score temporal para señales débiles
- embeddings o búsqueda semántica
- filtro explícito por lente: financiera, política, legal, tecnológica, etc.
