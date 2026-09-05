"""Bibliotheque des lecons "Cours" generees (backend/cours_seed/).

Contenu genere une fois par generate_cours_content.py a partir des chapitres
CONFIRMES dans le livret des programmes scolaires (cours_seed/curriculum_source.json),
puis committe dans git comme les PDF de pdf_library.py - jamais regenere a la
demande d'un eleve (cout, coherence, latence).
"""
import json
import os
import threading

_LOCK = threading.Lock()

SEED_DIR = os.path.join(os.path.dirname(__file__), "cours_seed")
_MANIFEST_PATH = os.path.join(SEED_DIR, "manifest.json")
_LESSONS_DIR = os.path.join(SEED_DIR, "lessons")

# Quand un pays n'a AUCUN chapitre confirme pour un niveau/matiere donnes, on
# propose plutot le contenu confirme du pays de reference le mieux documente
# de la region (meme tronc commun francophone), CLAIREMENT etiquete comme tel
# cote frontend (voir fallback_for/regional_source_pays) - jamais invente, on
# reutilise un vrai contenu source, juste pas celui du pays exact de l'eleve.
REGIONAL_REFERENCE_ORDER = {
    "college": ["cote_ivoire", "burkina_faso"],
    "lycee": ["cote_ivoire", "senegal"],
}


def _load_json(path: str):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def list_lessons(pays: str = "", niveau: str = "", matiere: str = "") -> list:
    with _LOCK:
        manifest = _load_json(_MANIFEST_PATH)

    filtered = manifest
    if pays:
        filtered = [m for m in filtered if m["pays"] == pays]
    if niveau:
        filtered = [m for m in filtered if m["niveau"] == niveau]
    if matiere:
        filtered = [m for m in filtered if m["matiere"] == matiere]

    if filtered or not (pays and niveau and matiere):
        return filtered

    # Rien de confirme pour ce pays precis sur ce niveau/matiere : on essaie
    # les pays de reference de la region, dans l'ordre, et on s'arrete au
    # premier qui a du contenu.
    for ref_pays in REGIONAL_REFERENCE_ORDER.get(niveau, []):
        if ref_pays == pays:
            continue
        candidates = [
            m for m in manifest
            if m["pays"] == ref_pays and m["niveau"] == niveau and m["matiere"] == matiere
        ]
        if candidates:
            return [
                {**m, "fallback_for": pays, "regional_source_pays": ref_pays}
                for m in candidates
            ]
    return []


def get_lesson(slug: str) -> dict | None:
    path = os.path.join(_LESSONS_DIR, f"{slug}.json")
    if not os.path.exists(path):
        return None
    with _LOCK:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
