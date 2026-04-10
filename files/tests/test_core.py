import json
import sys
from pathlib import Path

# Añadir el directorio padre al sys.path para encontrar wiki_utils.py
sys.path.append(str(Path(__file__).parent.parent))

# Importamos directamente de las utilidades lógicas para evitar cargar la UI
from wiki_utils import slugify, parse_json_response, extract_metadata

def test_slugify_unicode():
    print("Testing slugify...")
    assert slugify("Señal de Mercado") == "senal-de-mercado"
    assert slugify("Acción de Inversión") == "accion-de-inversion"
    assert slugify("Campaña 2026!") == "campana-2026"

def test_json_parsing_with_internal_braces():
    print("Testing JSON parsing...")
    raw_response = """
    {
        "resumen": "Nota con código",
        "paginas": [
            {
                "ruta": "wiki/test.md",
                "contenido": "Aquí hay un objeto: { key: 'val' } y más texto.",
                "confidence": 0.9
            }
        ]
    }
    """
    result = parse_json_response(raw_response)
    assert result["resumen"] == "Nota con código"
    assert "{ key: 'val' }" in result["paginas"][0]["contenido"]

def test_metadata_extraction_robustness():
    print("Testing metadata extraction...")
    content = """---
updated: 2026-04-10
confidence: 0.9
---
# Título
Este es el cuerpo.
---
Separador markdown que no debe romper nada.
"""
    meta = extract_metadata(content)
    assert meta["updated"] == "2026-04-10"
    assert meta["confidence"] == "0.9"

if __name__ == "__main__":
    try:
        test_slugify_unicode()
        test_json_parsing_with_internal_braces()
        test_metadata_extraction_robustness()
        print("\n✅ EXCELENTE: Todos los tests de núcleo pasaron exitosamente.")
        print("La inteligencia de la wiki está blindada contra regresiones.")
    except AssertionError as e:
        print(f"\n❌ ERROR DE TEST: Una validación falló.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR INESPERADO: {e}")
        sys.exit(1)
