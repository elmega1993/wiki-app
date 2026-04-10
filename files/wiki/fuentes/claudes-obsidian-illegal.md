# Claude + Obsidian: El Segundo Cerebro

**Fuente:** [@defileo](https://x.com/defileo/status/2042241063612502162) (X/Twitter)
**Fecha:** 2026-04-09
**Confidence:** 0.85 (Fuente secundaria / Análisis de usuario experto)

## Resumen Ejecutivo
El autor (@defileo, identificado como Leo) describe una arquitectura de "Segundo Cerebro" que combina **Claude Code** (LLM local/agent) con **Obsidian** (base de conocimiento en Markdown). La premisa central es que la gestión manual de un wiki personal es insostenible debido a la carga de mantenimiento; los LLMs automatizan la bookkeeping, permitiendo que el conocimiento compounding crezca indefinidamente.

## Arquitectura del Sistema
El sistema se basa en tres capas:
1.  **Raw Sources:** Fuentes inmutables (artículos, notas, transcripciones) almacenadas localmente (ej. `/raw-sources`).
2.  **The Wiki:** Una colección de archivos Markdown generados y mantenidos por el LLM (`/wiki/`). Incluye sumarios, páginas de entidades, conceptos y síntesis.
3.  **The Schema:** Un archivo de configuración (ej. `CLAUDE.md`) que define las reglas del juego para el LLM.

## Flujo de Operación
- **Ingest:** El usuario añade una fuente al raw folder y ejecuta un prompt a Claude. El LLM lee, extrae ideas, escribe sumarios, actualiza el índice (`index.md`) y vincula páginas existentes.
- **Query:** Se hacen preguntas contra el wiki. Las respuestas valiosas se filian de nuevo al wiki para no perderse en el chat.
- **Lint:** Revisiones periódicas (ej. semanal) para detectar contradicciones, páginas huérfanas o claims obsoletos.

## Componentes Clave
- **Obsidian:** Actúa como la IDE/interfaz visual y gestor de archivos local. Se recomienda usar plugins como `Dataview` para consultas estructuradas y `Marp` para presentaciones.
- **Claude Code:** El agente que ejecuta las tareas de escritura, lectura y mantenimiento del wiki.
- **Index.md:** Un catálogo orientado al contenido que permite navegación sin necesidad de embeddings complejos a pequeña escala.
- **Log.md:** Un registro cronológico (append-only) de todas las operaciones (ingests, queries, lint passes).

## Herramientas Sugeridas
- **Obsidian Web Clipper:** Para convertir artículos web a Markdown rápidamente.
- **qmd:** Motor de búsqueda local para wikis grandes (BM25 + vector search).
- **Morning Digest:** Script Python automatizado que lee el log y las acciones pendientes para generar un briefing matutino.

## Filosofía
"The human's job is to curate sources, ask good questions, and think about what it all means. The LLM's job is everything else." (El humano curatea y piensa; la máquina mantiene y procesa).

**Nota:** El autor concluye que esta combinación debería ser ilegal por su capacidad de potenciar el intelecto humano.

---
| Campo | Valor |
|-------|-------|
| Última actualización | 2026-04-10 11:15 |
| Confidence | 🟡 85% |

