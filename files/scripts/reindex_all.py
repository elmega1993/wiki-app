import sys
from pathlib import Path

# Añadir directorio raíz al path para importar wiki_utils
APP_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(APP_DIR))

from wiki_utils import VectorEngine

def reindex_all():
    WIKI_DIR = APP_DIR / "wiki"
    print(f"🚀 Iniciando re-indexación de la wiki en: {WIKI_DIR}")
    
    engine = VectorEngine(WIKI_DIR)
    
    # Recorrer todos los archivos markdown
    files = list(WIKI_DIR.rglob("*.md"))
    total = len(files)
    count = 0
    
    for path in files:
        # Saltar archivos del sistema
        if path.name in ("index.md", "log.md", "dashboard.md") or "templates" in str(path) or "backup" in str(path):
            continue
            
        try:
            rel_path = str(path.relative_to(WIKI_DIR))
            content = path.read_text(encoding="utf-8")
            engine.update_page(rel_path, content)
            count += 1
            if count % 10 == 0:
                print(f"✅ Procesados {count}/{total}...")
        except Exception as e:
            print(f"❌ Error procesando {path.name}: {e}")

    engine.save_store()
    print(f"\n✨ ¡ÉXITO! Se han indexado {count} páginas semánticamente.")
    print(f"El índice vectorial se guardó en: {WIKI_DIR}/.vector_store.json")

if __name__ == "__main__":
    reindex_all()
