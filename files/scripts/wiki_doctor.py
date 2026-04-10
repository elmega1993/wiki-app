import os
import re
from pathlib import Path

# Configuración de Rutas
WIKI_DIR = Path(__file__).parent.parent / "wiki"

def audit_integrity():
    print("🩺 Iniciando Auditoría Médica de la Wiki...")
    all_files = {}
    for p in WIKI_DIR.rglob("*.md"):
        if p.name in ("index.md", "log.md", "dashboard.md") or "templates" in str(p) or "backup" in str(p):
            continue
        all_files[p.stem] = p

    broken_links = []
    orphans = set(all_files.keys())
    
    for stem, path in all_files.items():
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"❌ Error leyendo {path.name}: {e}")
            continue

        links = re.findall(r"\[\[(.*?)\]\]", content)
        for link in links:
            clean_link = link.split("|")[0].strip()
            if clean_link not in all_files and clean_link not in ("index", "log", "dashboard"):
                broken_links.append((path.name, clean_link))
            if clean_link in orphans:
                orphans.remove(clean_link)

    print("\n--- REPORTE DE SALUD ---")
    if broken_links:
        print(f"❌ ENLACES ROTOS DETECTADOS: {len(broken_links)}")
        for file, target in broken_links:
            print(f"   - En '{file}' -> [[{target}]] (No existe)")
    else:
        print("✅ No se encontraron enlaces rotos.")

    if orphans:
        print(f"⚠️ PÁGINAS HUÉRFANAS DETECTADAS: {len(orphans)}")
        print("   (Nadie las referencia. Sugerencia: Ingerir nueva información para conectarlas)")
        for orphan in sorted(orphans)[:10]:
            print(f"   - {orphan}")
        if len(orphans) > 10:
            print(f"   ... y {len(orphans)-10} más.")
    else:
        print("✅ No hay páginas huérfanas. ¡Tu grafo está perfectamente tejido!")

    print("\n💡 Diagnóstico: " + ("Requiere atención" if broken_links else "Estable"))

if __name__ == "__main__":
    audit_integrity()
