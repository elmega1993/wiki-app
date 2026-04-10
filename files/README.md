# LLM Wiki

App de escritorio en Python que conecta con LM Studio para construir una wiki personal generalista orientada a inteligencia y acción.

La idea no es solo guardar información. La idea es transformar fuentes dispersas en:
- contexto útil
- señales legibles
- claims trazables
- narrativas, hipótesis y escenarios
- acciones mejor pensadas

## Qué cambió en esta versión
- la wiki dejó de estar organizada alrededor de “oportunidades”
- se agregaron `senales/`, `narrativas/`, `hipotesis/`, `escenarios/` y `acciones/`
- `raw/` se divide en `fuentes-originales/` y `assets/`
- `index.md`, `dashboard.md` y `log.md` los recompone la app
- el schema central vive en `wiki_schema.md`

## Estructura
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

## Requisitos
- Python 3.10+
- LM Studio corriendo en `http://localhost:1234`
- Opcional: `pdfminer.six`

```bash
pip install pdfminer.six
```

## Uso
```bash
python wiki_app.py
```

## Operaciones
- `＋ Ingerir fuente`: procesa texto, PDF o imagen y actualiza la wiki
- `🔍 Consultar wiki`: hace preguntas sobre el contenido compilado
- `🛠 Lint`: busca problemas, contradicciones y huecos
- `📡 Ver radar`: abre el radar operativo
- `⟳ Actualizar árbol`: refresca árbol e índices

## Documentación
La documentación completa está en [APP_DOCUMENTATION.md](./APP_DOCUMENTATION.md).
