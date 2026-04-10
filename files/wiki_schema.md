# LLM Wiki Schema — Reglas del Juego

## Estructura de Capas
- **raw/**: Fuentes inmutables. Nada se borra acá.
- **wiki/**: Conocimiento procesado y destilado.
- **wiki_schema.md**: Este documento (las reglas).

## REGLA DE CONECTIVIDAD (CRÍTICA)
- Usá SIEMPRE wikilinks de Obsidian `[[nombre-de-archivo]]` para referenciar otras páginas.
- PROHIBIDO usar texto plano o rutas como `wiki/fuentes/archivo.md` fuera de los corchetes dobles.
- El nombre del archivo dentro de los corchetes NO debe llevar la extensión .md.
- Si citás una fuente en "Trazabilidad", debés poner: "Fuente: [[nombre-de-la-fuente-generada]]".

## Categorías de la Wiki
1.  **fuentes/**: Resúmenes de artículos, hilos, imágenes o PDF.
2.  **senales/**: Fragmentos de información que sugieren un cambio o tendencia.
3.  **claims/**: Afirmaciones atómicas respaldadas por evidencia.
4.  **hipotesis/**: Tesis estructuradas que conectan múltiples claims.
5.  **escenarios/**: Simulaciones de futuro basadas en hipótesis.
6.  **acciones/**: Pasos concretos a seguir (investigar, validar, operar).
7.  **entidades/**: Personas, empresas o lugares clave.
8.  **narrativas/**: Cómo se cuenta una historia en el mercado/sociedad.

## Confidence Score (0.0 a 1.0)
- 0.9-1.0: 🟢 Fuente primaria, dato oficial verificable.
- 0.7-0.8: 🟡 Fuente secundaria confiable o análisis de experto.
- 0.4-0.6: 🟠 Rumor, señal débil o inferencia personal.
- 0.0-0.3: 🔴 Especulación o dato con evidencia contradictoria.

## Reglas de Ingest
- Generá un resumen ejecutivo corto al principio.
- Usá tablas para comparar datos cuando sea posible.
- Mantené siempre la sección `## Trazabilidad` al final con links a las fuentes originales.
- Integrá la información si la página ya existe. No la reemplaces totalmente.
- Si creás un claim, conectalo a una hipótesis existente si tiene relación.
