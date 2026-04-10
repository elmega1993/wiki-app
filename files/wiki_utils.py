import json
import re
import unicodedata
from pathlib import Path

def slugify(text: str) -> str:
    # QC-01: Normalizar Unicode para evitar errores de encoding
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"\s+", "-", text.strip().lower())
    text = re.sub(r"[^a-z0-9\-_]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "sin-titulo"

def extract_metadata(content: str) -> dict[str, str]:
    # QC-02: Parser robusto de frontmatter
    metadata = {"updated": "s/d", "confidence": "s/d", "status": "s/d", "type": "s/d"}
    in_frontmatter = False
    frontmatter_done = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "---":
            if not in_frontmatter and not frontmatter_done:
                in_frontmatter = True
            elif in_frontmatter:
                in_frontmatter = False
                frontmatter_done = True
            continue
        if in_frontmatter and ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            # Flexibilidad de llaves para fechas
            if key in {"updated", "updated_at", "date", "signal_date", "claim_date", "created_at"} and metadata["updated"] == "s/d":
                metadata["updated"] = value
            elif key == "status":
                metadata["status"] = value
            elif key == "type":
                metadata["type"] = value
            elif key == "confidence":
                metadata["confidence"] = value
    return metadata

def parse_json_response(raw: str) -> dict:
    # QC-03: Decodificación robusta con JSONDecoder
    raw = raw.strip()
    if "</think>" in raw:
        raw = raw[raw.rfind("</think>") + len("</think>"):]
    
    start = raw.find("{")
    if start == -1:
        raw = re.sub(r"```(?:json)?\s*", "", raw)
        raw = re.sub(r"```", "", raw).strip()
        start = raw.find("{")
        if start == -1: raise ValueError("No se encontró JSON en la respuesta")

    try:
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(raw, start)
        return obj
    except:
        # Fallback para casos extremos
        try:
            return json.loads(raw[start:raw.rindex("}")+1])
        except Exception as e:
            raise ValueError(f"Error parseando JSON: {e}")
