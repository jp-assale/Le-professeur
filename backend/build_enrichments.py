"""Construit cours_seed/enrichments/<slug>.json a partir de cours_seed/enrichments_src/*.json.

Les sources regroupent les complements pedagogiques par NOTION (« topic »,
ecrite une seule fois) et les associent aux lecons de chaque pays qui la
traitent (« map »). Ce script :
  - verifie que chaque slug associe existe bien dans cours_seed/lessons/ ;
  - remplace {EXAMEN} par l'examen de la lecon (BEPC, DEF, BFEM, BAC) ;
  - valide la structure (voir validate_enrichment) ;
  - ecrit un fichier par lecon, lu par cours_library.get_lesson().

Aucun appel reseau, aucun fichier de lessons/ modifie. Relancable a volonte.

Usage:
    python build_enrichments.py           # construit
    python build_enrichments.py --check   # valide seulement (code retour 1 si erreur)
"""
import glob
import json
import os
import sys

SEED_DIR = os.path.join(os.path.dirname(__file__), "cours_seed")
SRC_DIR = os.path.join(SEED_DIR, "enrichments_src")
OUT_DIR = os.path.join(SEED_DIR, "enrichments")
LESSONS_DIR = os.path.join(SEED_DIR, "lessons")

NIVEAUX_EXO = {"facile", "moyen", "examen"}
EXAMEN_COURT = {"Baccalaureat": "BAC"}


def validate_enrichment(slug: str, data: dict) -> list:
    """Liste des problemes de structure (vide si tout va bien)."""
    errs = []

    def need_list_of_str(key, mini=1):
        v = data.get(key)
        if v is None:
            return
        if not isinstance(v, list) or len(v) < mini or not all(isinstance(x, str) and x.strip() for x in v):
            errs.append(f"{slug}: '{key}' doit etre une liste de textes non vides")

    need_list_of_str("objectifs")
    need_list_of_str("prerequis")

    ar = data.get("a_retenir")
    if ar is not None:
        if not isinstance(ar, dict) or not (ar.get("points") or ar.get("formules")):
            errs.append(f"{slug}: 'a_retenir' doit contenir 'points' et/ou 'formules'")

    for i, e in enumerate(data.get("erreurs_frequentes") or []):
        if not (isinstance(e, dict) and e.get("erreur") and e.get("correction")):
            errs.append(f"{slug}: erreurs_frequentes[{i}] sans 'erreur'/'correction'")

    for i, x in enumerate(data.get("exercices") or []):
        if not (isinstance(x, dict) and x.get("enonce") and x.get("corrige")):
            errs.append(f"{slug}: exercices[{i}] sans 'enonce'/'corrige'")
            continue
        if x.get("niveau") and x["niveau"] not in NIVEAUX_EXO:
            errs.append(f"{slug}: exercices[{i}].niveau inconnu '{x['niveau']}'")

    m = data.get("methode_examen")
    if m is not None and not (isinstance(m, dict) and m.get("etapes")):
        errs.append(f"{slug}: 'methode_examen' sans 'etapes'")

    if "{EXAMEN}" in json.dumps(data, ensure_ascii=False):
        errs.append(f"{slug}: {{EXAMEN}} non remplace")
    return errs


def _substitute(value, examen: str):
    if isinstance(value, str):
        return value.replace("{EXAMEN}", examen)
    if isinstance(value, list):
        return [_substitute(v, examen) for v in value]
    if isinstance(value, dict):
        return {k: _substitute(v, examen) for k, v in value.items()}
    return value


def build(check_only: bool = False) -> int:
    errors = []
    outputs = {}
    for path in sorted(glob.glob(os.path.join(SRC_DIR, "*.json"))):
        with open(path, encoding="utf-8") as f:
            src = json.load(f)
        topics = src.get("topics", {})
        for slug, topic_id in src.get("map", {}).items():
            lesson_path = os.path.join(LESSONS_DIR, f"{slug}.json")
            if not os.path.exists(lesson_path):
                errors.append(f"{os.path.basename(path)}: lecon inconnue '{slug}'")
                continue
            if topic_id not in topics:
                errors.append(f"{os.path.basename(path)}: topic inconnu '{topic_id}' pour {slug}")
                continue
            if slug in outputs:
                errors.append(f"{slug}: associe deux fois (dans plusieurs sources ?)")
                continue
            with open(lesson_path, encoding="utf-8") as f:
                lesson = json.load(f)
            examen = EXAMEN_COURT.get(lesson.get("examen"), lesson.get("examen") or "l'examen")
            data = _substitute(topics[topic_id], examen)
            data = {"_topic": topic_id, **data}
            errors.extend(validate_enrichment(slug, data))
            outputs[slug] = data

    if errors:
        print("ERREURS :")
        for e in errors:
            print("  -", e)
        return 1

    if not check_only:
        os.makedirs(OUT_DIR, exist_ok=True)
        for slug, data in outputs.items():
            with open(os.path.join(OUT_DIR, f"{slug}.json"), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.write("\n")
        # Supprime les complements dont la source a disparu (renommage...).
        for path in glob.glob(os.path.join(OUT_DIR, "*.json")):
            if os.path.basename(path)[:-5] not in outputs:
                os.remove(path)
    print(f"OK : {len(outputs)} lecons enrichies" + (" (verification seule)" if check_only else ""))
    return 0


if __name__ == "__main__":
    sys.exit(build(check_only="--check" in sys.argv))
