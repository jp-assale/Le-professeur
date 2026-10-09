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
# Complements pedagogiques (objectifs, a retenir, erreurs frequentes,
# exercices corriges, methode d'examen) - un fichier <slug>.json par lecon,
# SUPERPOSE a la lecon d'origine au chargement : les fichiers de lessons/ ne
# sont jamais reecrits, une lecon sans complement s'affiche comme avant.
_ENRICH_DIR = os.path.join(SEED_DIR, "enrichments")
_METHODES_PATH = os.path.join(SEED_DIR, "methodes.json")

# Champs qu'un complement a le droit d'ajouter (jamais d'ecrasement du coeur
# de la lecon : intro/concept/example/quiz restent ceux d'origine).
ENRICH_FIELDS = (
    "objectifs", "prerequis", "a_retenir", "erreurs_frequentes",
    "exercices", "methode_examen",
)

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
        return _with_enrich_flag(filtered)

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
            return _with_enrich_flag([
                {**m, "fallback_for": pays, "regional_source_pays": ref_pays}
                for m in candidates
            ])
    return []


def _programme_order() -> dict:
    """(pays, niveau, matiere, serie, chapitre) -> rang dans la progression
    officielle (ordre des chapitres de curriculum_source.json). Le manifeste,
    lui, suit l'ordre de generation : « Calcul integral » pouvait apparaitre
    apres « Equations differentielles »."""
    order = {}
    for entry in _load_json(os.path.join(SEED_DIR, "curriculum_source.json")):
        for i, chap in enumerate(entry.get("chapitres", [])):
            key = (entry["pays"], entry["niveau"], entry["matiere"], entry.get("serie"), chap)
            order.setdefault(key, i)
    return order


def _with_enrich_flag(items: list) -> list:
    order = _programme_order()
    items = sorted(
        items,
        key=lambda m: order.get(
            (m["pays"], m["niveau"], m["matiere"], m.get("serie"), m["chapitre"]), 999
        ),
    )  # tri stable : sans rang connu, l'ordre du manifeste est conserve
    rich = enriched_slugs()
    if not rich:
        return items
    return [{**m, "enrichi": True} if m["slug"] in rich else m for m in items]


def _is_safe_slug(slug: str) -> bool:
    return bool(slug) and all(c.isalnum() or c == "-" for c in slug)


def _load_enrichment(slug: str) -> dict:
    path = os.path.join(_ENRICH_DIR, f"{slug}.json")
    data = _load_json(path)
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if k in ENRICH_FIELDS and v}


def enriched_slugs() -> set:
    if not os.path.isdir(_ENRICH_DIR):
        return set()
    return {f[:-5] for f in os.listdir(_ENRICH_DIR) if f.endswith(".json")}


def get_lesson(slug: str) -> dict | None:
    if not _is_safe_slug(slug):
        return None
    path = os.path.join(_LESSONS_DIR, f"{slug}.json")
    if not os.path.exists(path):
        return None
    with _LOCK:
        with open(path, "r", encoding="utf-8") as f:
            lesson = json.load(f)
        extra = _load_enrichment(slug)
    if extra:
        # Le complement ne remplace jamais un champ deja present dans la lecon.
        for k, v in extra.items():
            lesson.setdefault(k, v)
        lesson["enrichi"] = True
    return lesson


def list_methodes(niveau: str = "", matiere: str = "", pays: str = "") -> list:
    """Fiches methode transversales (dissertation, commentaire, resolution de
    probleme...). Une fiche sans `niveaux`/`matieres` vaut pour tous."""
    with _LOCK:
        fiches = _load_json(_METHODES_PATH)
    out = []
    for f in fiches:
        if niveau and f.get("niveaux") and niveau not in f["niveaux"]:
            continue
        if matiere and f.get("matieres") and matiere not in f["matieres"]:
            continue
        if pays and f.get("pays") and pays not in f["pays"]:
            continue
        out.append({k: f[k] for k in ("id", "titre", "matieres", "niveaux", "resume") if k in f})
    return out


def get_methode(methode_id: str) -> dict | None:
    with _LOCK:
        fiches = _load_json(_METHODES_PATH)
    return next((f for f in fiches if f.get("id") == methode_id), None)
