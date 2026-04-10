#!/usr/bin/env python3
"""
Migra las fuentes existentes a la taxonomía nueva de la wiki.
"""

from pathlib import Path
import json
import re

import wiki_app


def build_messages(source_path: Path) -> list[dict]:
    source_content = source_path.read_text(encoding="utf-8")
    context = "\n\n".join(
        filter(
            None,
            [
                wiki_app.read_wiki_context(),
                wiki_app.build_page_catalog(),
                wiki_app.build_relevant_context(source_path.stem, limit=10),
            ],
        )
    )

    prompt = f"""/no_think
Migrá esta fuente ya existente al esquema nuevo de la wiki.

IMPORTANTE:
- No recrees la página de `fuentes/` salvo que sea estrictamente necesario.
- Priorizá crear o actualizar páginas en `senales/`, `claims/`, `narrativas/`, `hipotesis/`, `escenarios/` y `acciones/`.
- No fuerces una página en cada categoría; creá solo lo que realmente tenga sentido.
- Si algo es débil o especulativo, tratálo como señal o hipótesis, no como hecho.
- Si una página ya existe conceptualmente, actualizala en vez de duplicarla.
- Mantené trazabilidad a `{wiki_app.wiki_relpath(source_path)}`.

Fuente a migrar:
### {wiki_app.wiki_relpath(source_path)}
{source_content}

---
Contexto actual de la wiki:
{context}
"""

    return [
        {"role": "system", "content": wiki_app.load_schema()},
        {"role": "user", "content": prompt},
    ]


def migrate_source(source_path: Path) -> dict:
    raw = wiki_app.call_lm_studio(build_messages(source_path), timeout=180)
    result = wiki_app.parse_json_response(raw)
    saved = wiki_app.save_pages(result.get("paginas", []))
    return {
        "source": source_path.name,
        "saved": saved,
        "summary": result.get("resumen", "Migrado."),
    }


def main():
    wiki_app.ensure_dirs()
    log_text = (wiki_app.WIKI_DIR / "log.md").read_text(encoding="utf-8") if (wiki_app.WIKI_DIR / "log.md").exists() else ""
    already_done = set(re.findall(r"migration \| ([^\n]+)", log_text))
    migrated = []
    for source_path in sorted((wiki_app.WIKI_DIR / "fuentes").glob("*.md")):
        if source_path.name in already_done:
            continue
        outcome = migrate_source(source_path)
        migrated.append(outcome)
        wiki_app.append_log_entry(
            "migration",
            source_path.name,
            [f"Resumen: {outcome['summary']}"]
            + [f"Página actualizada: `{wiki_app.wiki_relpath(path)}` | confidence {score:.0%}" for path, score in outcome["saved"]],
        )
        wiki_app.refresh_compiled_views()

    print(json.dumps(
        {
            "migrated_sources": len(migrated),
            "created_pages": sum(len(item["saved"]) for item in migrated),
            "sources": [
                {
                    "source": item["source"],
                    "summary": item["summary"],
                    "pages": [wiki_app.wiki_relpath(path) for path, _ in item["saved"]],
                }
                for item in migrated
            ],
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
