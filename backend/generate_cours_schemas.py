"""Genere un schema simplifie (flux / cycle / hierarchie / parties) pour chaque
lecon de SVT et de Physique-Chimie deja presente dans cours_seed/lessons/.

Principe (meme garde-fou que le reste des cours : jamais de contenu invente) :
1. Un modele genere la STRUCTURE du schema (texte JSON, jamais du SVG) en
   s'appuyant uniquement sur le contenu de la lecon et sur des connaissances
   de manuel scolaire etablies. Il peut repondre "aucun schema" si le chapitre
   ne s'y prete pas.
2. Un second modele, plus strict, VERIFIE chaque element contre la lecon et
   les connaissances scolaires : ok / a corriger / rejete. Un schema corrige
   doit repasser la verification. Seuls les schemas valides sont gardes.
3. Le dessin est fait par le code de l'appli (diagram-viewer.js).

Ne modifie aucun autre champ de la lecon. Resumable : saute les lecons qui
ont deja "schema_status". COURS_GEN_LIMIT limite le nombre de lecons traitees.
Rapport detaille dans cours_seed/schema_report.json.

Usage:
    python generate_cours_schemas.py
    COURS_GEN_LIMIT=3 python generate_cours_schemas.py
"""
import glob
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

SEED_DIR = os.path.join(os.path.dirname(__file__), "cours_seed")
LESSONS_DIR = os.path.join(SEED_DIR, "lessons")
REPORT_PATH = os.path.join(SEED_DIR, "schema_report.json")

GEN_MODEL = os.environ.get("SCHEMA_GEN_MODEL", "claude-sonnet-5")
VERIFY_MODEL = os.environ.get("SCHEMA_VERIFY_MODEL", "claude-sonnet-5")
LIMIT = int(os.environ.get("COURS_GEN_LIMIT", "0")) or None
MATIERES = {"SVT", "Physique-Chimie"}
TYPES = {"flux", "cycle", "hierarchie", "parties"}

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

FORMAT_HINT = (
    '{"schema": {"type": "flux|cycle|hierarchie|parties", "titre": "...", '
    '"racine": "... (hierarchie seulement)", "centre": "... (parties seulement)", '
    '"items": [{"label": "...", "detail": "..."}]}}'
)


def lesson_context(lesson: dict) -> str:
    steps = " | ".join(lesson["example"]["steps"][:6]) if lesson.get("example") else ""
    return (
        f"Chapitre : {lesson['chapitre']} ({lesson['matiere']}, niveau {lesson['niveau']}, "
        f"{lesson['pays']})\n"
        f"Mise en situation : {lesson['intro']['body']}\n"
        f"Concept : {lesson['concept']['explanation']}\n"
        f"Regle cle : {lesson['concept'].get('highlight', '')}\n"
        f"Exemple : {lesson['example']['problem']} Etapes : {steps}"
    )


def generation_prompt(lesson: dict, feedback=None) -> str:
    retour = (
        "\nUn premier essai a ete REFUSE par le correcteur pour ces raisons - "
        "propose un schema different qui les evite :\n- " + "\n- ".join(feedback) + "\n"
    ) if feedback else ""
    return (
        "Tu prepares un schema simplifie pour une lecon scolaire, a afficher sous "
        "le concept. Voici la lecon :\n\n"
        f"{lesson_context(lesson)}\n\n"
        "Choisis le type de schema le plus adapte :\n"
        "- flux : etapes enchainees (processus, reaction, chaine de transformations)\n"
        "- cycle : UNIQUEMENT une vraie boucle (le dernier element ramene au premier), "
        "3 a 6 elements - si deux produits apparaissent en meme temps, n'utilise pas cycle\n"
        "- hierarchie : une racine et ses branches (classification, organisation)\n"
        "- parties : un element central (organe, appareil, objet, montage) et ses "
        "parties legendees avec leur role\n\n"
        f"{retour}"
        "Regles strictes :\n"
        "- Utilise UNIQUEMENT ce qui figure dans la lecon ou des connaissances de "
        "manuel scolaire etablies et exactes pour ce niveau. N'invente jamais un "
        "element, un nombre ou une valeur. En cas de doute sur un element, ne le "
        "mets pas.\n"
        "- 3 a 8 elements. label : 1 a 4 mots. detail : 12 mots maximum, facultatif.\n"
        "- Ecris tous les textes en francais correct AVEC tous les accents et cedilles "
        "(é, è, ê, à, ù, ç...), comme dans la lecon. Pas d'emoji. Formules : texte simple "
        "(ex: CO2, H2O, U = R x I).\n"
        "- Pour un circuit electrique ou un montage, utilise 'parties' (composants "
        "et role de chacun) - tu ne peux pas dessiner de circuit.\n"
        "- Si le chapitre ne se prete pas a un schema utile (pur calcul, "
        "definition sans structure), reponds {\"schema\": null, \"raison\": \"...\"}.\n"
        "- Reponds UNIQUEMENT avec un objet JSON valide, sans texte autour, sans "
        f"balises markdown, dans ce format : {FORMAT_HINT}"
    )


def verification_prompt(lesson: dict, schema: dict) -> str:
    return (
        "Tu es un correcteur scientifique STRICT. Voici une lecon scolaire et un "
        "schema simplifie qui doit l'illustrer.\n\n"
        f"{lesson_context(lesson)}\n\n"
        f"Schema a verifier :\n{json.dumps(schema, ensure_ascii=False)}\n\n"
        "Verifie chaque element et chaque detail : exactitude scientifique au "
        "niveau scolaire indique, coherence avec la lecon, ordre correct des "
        "etapes, absence de contresens, de vague trompeur ou d'element douteux. "
        "Reponds UNIQUEMENT avec un objet JSON valide, sans texte autour : "
        '{"verdict": "ok" | "corriger" | "rejeter", "problemes": ["..."], '
        '"schema_corrige": null ou un schema complet au meme format}. '
        "'ok' seulement si TOUT est juste. 'corriger' si des erreurs precises "
        "sont corrigeables : donne alors le schema complet corrige. 'rejeter' "
        "si le schema est globalement faux, trompeur ou inutile."
    )


def parse_json(raw: str) -> dict:
    """Extrait le premier objet JSON de la reponse (le modele peut ajouter du
    texte ou des balises autour malgre la consigne)."""
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("pas de JSON dans la reponse : " + raw[:120].replace("\n", " "))
    return json.loads(raw[start:end + 1])


def ask(model: str, prompt: str, max_tokens: int = 6000) -> dict:
    t0 = time.time()
    response = client.messages.create(
        model=model, max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    print(f"    appel {model} : {time.time() - t0:.1f}s", flush=True)
    return parse_json("".join(b.text for b in response.content if b.type == "text"))


def clean_schema(raw):
    """Valide et normalise un schema ; None s'il est inutilisable."""
    if not isinstance(raw, dict):
        return None
    t = str(raw.get("type", "")).strip().lower()
    if t not in TYPES:
        return None
    items = []
    for it in raw.get("items") or []:
        if not isinstance(it, dict):
            continue
        label = str(it.get("label", "")).strip()[:40]
        detail = str(it.get("detail", "") or "").strip()[:90]
        if label:
            items.append({"label": label, "detail": detail})
    items = items[:8]
    if len(items) < 3:
        return None
    spec = {"type": t, "titre": str(raw.get("titre", "")).strip()[:60], "items": items}
    if t == "hierarchie":
        spec["racine"] = str(raw.get("racine", "")).strip()[:40]
        if not spec["racine"]:
            return None
    if t == "parties":
        spec["centre"] = str(raw.get("centre", "")).strip()[:40]
        if not spec["centre"]:
            return None
    if t == "cycle" and not (3 <= len(items) <= 6):
        spec["type"] = "flux"
    return spec


MAX_ROUNDS = 3  # generation -> verification -> (correction ou nouvel essai guide) x3
WORKERS = int(os.environ.get("SCHEMA_WORKERS", "4"))
_lock = threading.Lock()


def process(lesson: dict):
    """Retourne (schema ou None, statut, details pour le rapport).

    Boucle : le correcteur juge le schema ; s'il propose une correction valide
    on la re-verifie, sinon on regenere en lui donnant les problemes releves.
    Un schema n'est garde que si le correcteur repond "ok" sur sa version
    finale - aucune exigence n'est abaissee, on laisse seulement plusieurs
    chances de repartir des remarques."""
    feedback = None
    historique = []
    current = None
    corrige = False

    for _ in range(MAX_ROUNDS):
        if current is None:
            generated = ask(GEN_MODEL, generation_prompt(lesson, feedback))
            if generated.get("schema") is None:
                if historique:
                    break
                return None, "aucun", {"raison": generated.get("raison", "")}
            current = clean_schema(generated.get("schema"))
            if current is None:
                feedback = ["format invalide : respecte exactement le format demande"]
                continue

        verdict = ask(VERIFY_MODEL, verification_prompt(lesson, current))
        problemes = verdict.get("problemes") or []
        if verdict.get("verdict") == "ok":
            return current, ("corrige" if corrige else "ok"), {"problemes": historique}

        historique.extend(problemes)
        fixed = clean_schema(verdict.get("schema_corrige")) if verdict.get("verdict") == "corriger" else None
        if fixed is not None:
            current, corrige = fixed, True       # re-verifie au tour suivant
        else:
            current, feedback = None, problemes  # nouvel essai guide par les remarques

    return None, "rejete", {"problemes": historique}


def handle(path, lesson, report, counts, failed):
    try:
        schema, status, details = process(lesson)
    except Exception as exc:
        with _lock:
            print(f"  [ECHEC] {lesson['slug']} : {exc}", flush=True)
            failed.append(lesson["slug"])
        return
    with _lock:
        lesson["schema"] = schema
        lesson["schema_status"] = status
        with open(path, "w", encoding="utf-8") as f:
            json.dump(lesson, f, ensure_ascii=False, indent=2)
        report[lesson["slug"]] = {"statut": status, "chapitre": lesson["chapitre"], **details}
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        counts[status] += 1
        print(f"  [{status.upper()}] {lesson['slug']}", flush=True)


def main():
    paths = sorted(glob.glob(os.path.join(LESSONS_DIR, "*.json")))
    report = json.load(open(REPORT_PATH, encoding="utf-8")) if os.path.exists(REPORT_PATH) else {}
    counts = {"ok": 0, "corrige": 0, "aucun": 0, "rejete": 0}
    failed = []

    todo = []
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            lesson = json.load(f)
        if lesson["matiere"] in MATIERES and "schema_status" not in lesson:
            todo.append((path, lesson))
    if LIMIT:
        todo = todo[:LIMIT]
    print(f"{len(todo)} lecon(s) a traiter, {WORKERS} en parallele.", flush=True)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for path, lesson in todo:
            pool.submit(handle, path, lesson, report, counts, failed)

    print(f"\nTermine. Detail : {counts}. Echecs : {len(failed)}.")
    if failed:
        print("Slugs en echec (relancer le script les reprendra) :", failed)


if __name__ == "__main__":
    main()
