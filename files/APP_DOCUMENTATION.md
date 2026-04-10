# App Documentation: LLM Wiki (Brain Shell)

Esta aplicación es una implementación robusta del patrón "LLM Wiki" (Karpathy), diseñada para transformar información dispersa en un ecosistema de conocimiento estructurado, trazable e interconectado.

## Características Principales (Update 2026-04)

### 1. Ingesta Inteligente y Segura
- **Inbox No Destructivo**: La app ya no elimina los archivos originales del usuario. Se respeta la inmutabilidad de la capa `raw/`.
- **Smart Merge**: Al actualizar páginas existentes, el modelo recibe el contenido anterior para INTEGRAR la información.
- **Backups Automáticos**: Cada actualización de página genera un archivo `.md.bak` de seguridad.
- **Batch Processing**: Ingesta masiva con soporte real para PDFs e imágenes.

### 2. Conectividad Dinámica (Anti-Orphan)
- **Active Connectivity**: Análisis en tiempo real de páginas huérfanas.
- **Inyección de Objetivos**: El LLM recibe objetivos de enlace para evitar que el conocimiento quede aislado.

### 3. Arquitectura Modular y Testing
- **Separación de Capas**: La lógica de inteligencia vive en `wiki_utils.py`, aislada de la interfaz gráfica (`wiki_app.py`).
- **Suite de Tests**: Ejecutando `python3 tests/test_core.py` se validan las funciones críticas de slugify, parseo de JSON y metadatos.
- **Wiki Doctor**: Herramienta de mantenimiento (`scripts/wiki_doctor.py`) para auditar la salud del grafo (links rotos y huérfanos).

---

## Estructura de Archivos
```text
files/
  wiki_app.py          # Interfaz de usuario (Tkinter) y Orquestación.
  wiki_utils.py        # INTELIGENCIA: Slugify, Parsers y Lógica pura.
  wiki_schema.md       # Reglas maestras para el LLM.
  tests/
    test_core.py       # Suite de tests automáticos.
  scripts/
    wiki_doctor.py     # Auditor de integridad de la wiki.
  raw/                 # Inbox inmutable.
  wiki/                # Cerebro sintético interconectado.
```

## Mantenimiento y Calidad
Para mantener tu wiki en perfecto estado, se recomienda:
1. **Auditoría Semanal**: Ejecutar `python3 scripts/wiki_doctor.py`.
2. **Validación de Código**: Correr `python3 tests/test_core.py` antes de cualquier modificación manual en `wiki_utils.py`.

---
*Documentación actualizada al 10 de Abril de 2026 post-modularización.*
