import json
import re
import unicodedata
import hashlib
import sys
from pathlib import Path

try:
    from fastembed import TextEmbedding
    import numpy as np
except ImportError:
    TextEmbedding = None
    np = None

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

class VectorEngine:
    def __init__(self, wiki_dir: Path, model_name="BAAI/bge-small-en-v1.5"):
        self.wiki_dir = Path(wiki_dir)
        self.vector_file = self.wiki_dir / ".vector_store.json"
        self.model_name = model_name
        self._model = None
        self.store = self._load_store()

    @property
    def model(self):
        if self._model is None and TextEmbedding:
            try:
                print(f"📥 Cargando modelo de embeddings ({self.model_name})...")
                self._model = TextEmbedding(model_name=self.model_name)
            except Exception as e:
                print(f"❌ Error cargando modelo: {e}")
                return None
        return self._model

    def _load_store(self) -> dict:
        if self.vector_file.exists():
            try:
                return json.loads(self.vector_file.read_text(encoding="utf-8"))
            except:
                return {}
        return {}

    def save_store(self):
        try:
            self.vector_file.write_text(json.dumps(self.store, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"❌ Error guardando vectores: {e}")

    def update_page(self, rel_path: str, content: str):
        if not self.model: return
        
        new_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
        
        # Evitar re-vectorizar si no hay cambios
        if self.store.get(rel_path, {}).get("hash") == new_hash:
            return

        try:
            print(f"🧠 Vectorizando: {rel_path}...")
            # fastembed devuelve un iterador de arrays numpy
            embeddings = list(self.model.embed([content]))
            vector = embeddings[0].tolist()
            
            self.store[rel_path] = {
                "vector": vector,
                "hash": new_hash
            }
            self.save_store()
        except Exception as e:
            print(f"❌ Error vectorizando {rel_path}: {e}")

    def search(self, query: str, top_k=5) -> list[tuple[str, float]]:
        if not self.model or not self.store or np is None:
            return []
        
        try:
            query_vector = list(self.model.embed([query]))[0]
            
            results = []
            for path, data in self.store.items():
                vec = np.array(data["vector"])
                # Similitud de Coseno (vectores BGE vienen normalizados)
                score = np.dot(query_vector, vec)
                results.append((path, float(score)))
            
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:top_k]
        except Exception as e:
            print(f"❌ Error en búsqueda vectorial: {e}")
            return []
