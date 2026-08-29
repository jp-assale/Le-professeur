"""Bibliotheque de VRAIS sujets d'examens en PDF (contrairement a epreuves.py
qui contient des exercices originaux ecrits par l'IA).

Deux sources, fusionnees a la lecture :

1) "seed" (backend/pdf_seed/) : PDF + manifest.json COMMITTES DANS GIT.
   Survivent a tous les redeploiements car ils font partie du code livre.
   C'est la source a utiliser pour tout PDF qu'on veut garder durablement -
   donne le fichier a l'assistant pour qu'il l'ajoute ici et le commit.

2) "runtime" (DATA_DIR/pdfs/) : PDF ajoutes en direct via POST
   /api/admin/pdf-sujets (protege par ADMIN_TOKEN). Pratique pour tester
   rapidement, mais sur Render (plan gratuit) le disque est EPHEMERE - tout
   fichier ajoute ici disparait au prochain redeploiement. A ne pas
   considerer comme un stockage definitif.
"""
import json
import os
import threading
import uuid
from datetime import date

from paths import DATA_DIR

_LOCK = threading.Lock()

SEED_DIR = os.path.join(os.path.dirname(__file__), "pdf_seed")
_SEED_MANIFEST_PATH = os.path.join(SEED_DIR, "manifest.json")
os.makedirs(SEED_DIR, exist_ok=True)

_RUNTIME_META_PATH = os.path.join(DATA_DIR, "pdf_sujets.json")
RUNTIME_PDF_DIR = os.path.join(DATA_DIR, "pdfs")
os.makedirs(RUNTIME_PDF_DIR, exist_ok=True)

_CORRIGER_CACHE_PATH = os.path.join(DATA_DIR, "pdf_corriger_cache.json")
_CACHE_LOCK = threading.Lock()


def _load_json(path: str) -> list:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def _load_seed() -> list:
    return [dict(i, _origin="seed") for i in _load_json(_SEED_MANIFEST_PATH)]


def _load_runtime() -> list:
    return [dict(i, _origin="runtime") for i in _load_json(_RUNTIME_META_PATH)]


def _save_runtime(data: list) -> None:
    with open(_RUNTIME_META_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def _all() -> list:
    return _load_seed() + _load_runtime()


def list_pdf_sujets(pays: str | None = None, niveau: str | None = None,
                     matiere: str | None = None) -> list:
    items = _all()
    if pays:
        items = [i for i in items if i["pays"] == pays]
    if niveau:
        items = [i for i in items if i["niveau"] == niveau]
    if matiere:
        items = [i for i in items if i["matiere"] == matiere]
    return [
        {k: v for k, v in i.items() if k not in ("filename", "_origin", "_source")}
        for i in items
    ]


def get_pdf_sujet(sujet_id: str) -> dict | None:
    for i in _all():
        if i["id"] == sujet_id:
            return i
    return None


def get_pdf_dir(entry: dict) -> str:
    return SEED_DIR if entry.get("_origin") == "seed" else RUNTIME_PDF_DIR


def add_pdf_sujet(pays: str, niveau: str, matiere: str, annee: int, titre: str,
                   source: str, file_bytes: bytes) -> dict:
    """Ajout RUNTIME (ephemere sur Render gratuit - voir docstring du module).
    Pour un ajout permanent, transmettre le fichier a l'assistant pour qu'il
    l'ajoute a pdf_seed/manifest.json et le commit."""
    sujet_id = uuid.uuid4().hex[:16]
    filename = f"{sujet_id}.pdf"
    with open(os.path.join(RUNTIME_PDF_DIR, filename), "wb") as f:
        f.write(file_bytes)

    entry = {
        "id": sujet_id,
        "pays": pays,
        "niveau": niveau,
        "matiere": matiere,
        "annee": annee,
        "titre": titre,
        "source": source,
        "filename": filename,
        "added": date.today().isoformat(),
    }
    with _LOCK:
        data = _load_json(_RUNTIME_META_PATH)
        data.append(entry)
        _save_runtime(data)
    return dict(entry, _origin="runtime")


def delete_pdf_sujet(sujet_id: str) -> bool:
    with _LOCK:
        data = _load_json(_RUNTIME_META_PATH)
        entry = next((i for i in data if i["id"] == sujet_id), None)
        if not entry:
            return False  # les PDF "seed" ne se suppriment pas via l'API - editer le repo
        data = [i for i in data if i["id"] != sujet_id]
        _save_runtime(data)
        try:
            os.remove(os.path.join(RUNTIME_PDF_DIR, entry["filename"]))
        except OSError:
            pass
        return True


def get_cached_corriger(sujet_id: str) -> str | None:
    """Reponse deja generee pour la premiere ouverture de ce sujet - evite de
    rappeler l'IA (cout, latence) et surtout garantit que tous les eleves qui
    ouvrent le meme sujet voient exactement le meme enonce retranscrit,
    au lieu d'une nouvelle transcription potentiellement differente a chaque fois."""
    with _CACHE_LOCK:
        cache = _load_json(_CORRIGER_CACHE_PATH)
    return cache.get(sujet_id) if isinstance(cache, dict) else None


def set_cached_corriger(sujet_id: str, answer: str) -> None:
    with _CACHE_LOCK:
        raw = _load_json(_CORRIGER_CACHE_PATH)
        cache = raw if isinstance(raw, dict) else {}
        cache[sujet_id] = answer
        with open(_CORRIGER_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
