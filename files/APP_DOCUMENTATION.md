# App Documentation: LLM Wiki (Brain Shell)

Esta aplicación es una implementación robusta del patrón "LLM Wiki" (Karpathy), diseñada para transformar información dispersa en un ecosistema de conocimiento estructurado, trazable e interconectado.

## Características Principales (Update 2026-04)

### 1. Ingesta Inteligente y Segura
- **Inbox No Destructivo**: A diferencia de versiones anteriores, la app ya no elimina los archivos originales del usuario. Se respeta la inmutabilidad de la capa `raw/`.
- **Smart Merge**: Al actualizar páginas existentes, el modelo recibe el contenido anterior y está instruido para INTEGRAR la información, no para sobrescribirla ciegamente.
- **Backups Automáticos**: Cada actualización de página genera un archivo `.md.bak` de seguridad.
- **Batch Processing**: Ingesta masiva de carpetas con soporte real para extracción de texto en PDFs e imágenes.

### 2. Conectividad Dinámica (Anti-Orphan)
- **Active Connectivity**: El sistema analiza la wiki en tiempo real para detectar páginas huérfanas (sin enlaces entrantes).
- **Inyección de Objetivos**: Durante la ingesta, el LLM recibe estas páginas huérfanas como objetivos para forzar la creación de enlaces bidireccionales, evitando que tu conocimiento quede aislado en "islas".

### 3. Integridad de Datos
- **FILE_LOCK**: Sistema de bloqueo de concurrencia que garantiza que las escrituras en archivos maestros (`log.md`, `index.md`, `dashboard.md`) sean atómicas y seguras.
- **Unicode Robustness**: Función `slugify` mejorada que soporta caracteres latinos (`ñ`, acentos) y normalización Unicode para evitar nombres de archivo corruptos.
- **Parseo Profesional**: Uso de `raw_decode` para manejar respuestas del LLM con caracteres especiales y bloques de código complejos.

### 4. Experiencia de Usuario (UX)
- **Obsidian Native**: Generación de `[[wikilinks]]` puros para una visualización fluida del Grafo de Conocimiento.
- **Desktop Launcher**: Icono premium y lanzador integrado en el escritorio Linux para acceso rápido.
- **Feedback Visual**: Diálogos de confirmación y barras de estado detalladas durante el procesamiento.

---

## Estructura de Carpetas
```text
files/
  wiki_app.py          # Orquestador principal (Tkinter + LLM Logic)
  wiki_schema.md       # Cerebro/Reglas compartidas con el modelo
  raw/                 # Almacén inmutable de fuentes
    fuentes-originales/
    assets/            # PDFs e Imágenes originales
  wiki/                # Tu cerebro sintético
    fuentes/           # Resúmenes trazables
    senales/           # Indicios temporales
    claims/            # Hechos atómicos
    hipotesis/         # Tesis de trabajo
    escenarios/        # Simulaciones
    acciones/          # Pasos operativos
    consultas/         # Preguntas archivadas
    templates/         # Guías de formato
```

## Flujos de Trabajo Maestros

### Ingesta (La Siembra)
1. El usuario selecciona fuentes (Texto, PDF, Imágenes, Carpetas).
2. La app genera un contexto relevante (Búsqueda por palabras clave + Catalog + Log + Huérfanas).
3. El LLM extrae señales y crea/actualiza páginas.
4. Se generan backups y se actualiza el `index.md` automáticamente.

### Consulta (La Cosecha)
1. Pregunta libre sobre la base de conocimiento.
2. Recuperación de contexto basada en relevancia semántica simple.
3. Respuesta del LLM con links activos a las fuentes.
4. Botón "Guardar en Wiki" para preservar respuestas valiosas.

---

## Notas Técnicas
- **Motor**: Diseñado para ser usado con LM Studio (Local Inference).
- **Timeouts**: 180s para ingestas complejas.
- **Soporte PDF**: Extracción basada en PDFMiner.
- **Versionado**: Integración nativa con `git` sugerida para el directorio de la wiki.

---
*Documentación actualizada al 10 de Abril de 2026.*
