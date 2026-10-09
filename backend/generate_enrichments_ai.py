"""Genere par IA les complements pedagogiques des lecons qui n'en ont pas encore.

Les complements ecrits a la main (cours_seed/enrichments_src/college_*.json)
restent prioritaires : ce script ne traite QUE les lecons absentes de toutes
les sources. Pour chaque lecon :
  1. generation (objectifs, a retenir, erreurs frequentes, 3 exercices
     facile/moyen/examen avec corrige, methode d'examen) en sortie structuree ;
  2. verification par un SECOND appel qui refait chaque exercice a l'aveugle
     et signale les corriges faux : un exercice signale est retire, et la
     lecon est rejetee s'il reste moins de 2 exercices ;
  3. ajout dans cours_seed/enrichments_src/zz_ia_generes.json (resumable).
Puis lancer `python build_enrichments.py` et RELIRE le diff avant de committer.

Comme les lecons elles-memes, ce contenu est genere une fois et committe -
jamais a la demande d'un eleve (cout, coherence, latence).

Usage (cle ANTHROPIC_API_KEY dans backend/.env, SDK anthropic >= 1.x) :
    python generate_enrichments_ai.py                 # toutes les lecons manquantes
    ENRICH_LIMIT=5 python generate_enrichments_ai.py  # lot de validation
    ENRICH_MATIERE=Physique-Chimie python generate_enrichments_ai.py
"""
import glob
import json
import os
import sys
from typing import List, Literal, Optional

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

from build_enrichments import validate_enrichment
from curriculum import CONTEXTE_PAYS, niveau_label, pays_avec_preposition

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

SEED_DIR = os.path.join(os.path.dirname(__file__), "cours_seed")
SRC_DIR = os.path.join(SEED_DIR, "enrichments_src")
OUT_PATH = os.path.join(SRC_DIR, "zz_ia_generes.json")
MANIFEST_PATH = os.path.join(SEED_DIR, "manifest.json")
LESSONS_DIR = os.path.join(SEED_DIR, "lessons")

MODEL = os.environ.get("ENRICH_MODEL", "claude-opus-5-5")
LIMIT = int(os.environ.get("ENRICH_LIMIT", "0")) or None
MATIERE = os.environ.get("ENRICH_MATIERE") or None

client = anthropic.Anthropic()


class Erreur(BaseModel):
    erreur: str
    correction: str


class Exercice(BaseModel):
    niveau: Literal["facile", "moyen", "examen"]
    enonce: str
    indice: str
    corrige: List[str]


class ARetenir(BaseModel):
    points: List[str]
    formules: List[str]


class Methode(BaseModel):
    titre: str
    etapes: List[str]


class Enrichissement(BaseModel):
    objectifs: List[str]
    prerequis: List[str]
    a_retenir: ARetenir
    erreurs_frequentes: List[Erreur]
    exercices: List[Exercice]
    methode_examen: Methode


class Verdict(BaseModel):
    index: int
    correct: bool
    remarque: Optional[str] = None


class Verification(BaseModel):
    verdicts: List[Verdict]


SYSTEM = (
    "Tu es un professeur expérimenté et un concepteur de programmes scolaires "
    "d'Afrique de l'Ouest francophone (collège et lycée). Tu écris en français "
    "correct et accentué, pour des élèves, avec des exemples concrets et locaux. "
    "Tu ne cites jamais de chiffres officiels (coefficients, barèmes nationaux) "
    "dont tu n'es pas sûr."
)


def _done_slugs() -> set:
    done = set()
    for path in glob.glob(os.path.join(SRC_DIR, "*.json")):
        with open(path, encoding="utf-8") as f:
            done.update(json.load(f).get("map", {}).keys())
    return done


def _text(response) -> str:
    return next((b.text for b in response.content if b.type == "text"), "")


def generate(lesson: dict) -> Enrichissement | None:
    examen = "BAC" if lesson["examen"] == "Baccalaureat" else lesson["examen"]
    ctx = CONTEXTE_PAYS.get(lesson["pays"], {})
    serie = f", série {lesson['serie']}" if lesson.get("serie") else ""
    cours = json.dumps(
        {k: lesson.get(k) for k in ("chapitre", "intro", "concept", "example")},
        ensure_ascii=False,
    )
    prompt = (
        f"Leçon : « {lesson['chapitre']} », {lesson['matiere']}, "
        f"{niveau_label(lesson['pays'], lesson['niveau'])}{serie}, "
        f"{pays_avec_preposition(lesson['pays'])}. Monnaie : {ctx.get('monnaie', 'FCFA')}.\n\n"
        f"Contenu déjà présenté à l'élève :\n{cours}\n\n"
        "Écris les compléments pédagogiques de cette leçon, cohérents avec ce contenu :\n"
        "- objectifs : 3 ou 4 capacités, formulées avec un verbe d'action ;\n"
        "- prerequis : 2 ou 3 notions à maîtriser avant ;\n"
        "- a_retenir : 4 à 6 points essentiels + les formules/règles/dates clés "
        "(liste vide si la matière n'en a pas) ;\n"
        "- erreurs_frequentes : 3 erreurs réelles d'élèves, chacune avec sa correction ;\n"
        "- exercices : EXACTEMENT 3, niveaux facile, moyen, examen (type "
        f"{examen}, contexte concret). Le corrigé est une liste d'étapes "
        "rédigées ; pour un calcul, chaque étape montre le calcul et l'unité. "
        "VÉRIFIE chaque calcul deux fois avant de l'écrire. En matière littéraire, "
        "le corrigé donne les éléments attendus et un plan ;\n"
        f"- methode_examen : titre commençant par « Au {examen} : », 3 à 5 étapes.\n"
        "Notation : symboles Unicode (², √, ×, ≤, →) plutôt que LaTeX."
    )
    response = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        output_config={"effort": "high"},
        messages=[{"role": "user", "content": prompt}],
        output_format=Enrichissement,
    )
    if response.stop_reason == "refusal":
        return None
    return response.parsed_output


def verify(lesson: dict, data: Enrichissement) -> Enrichissement | None:
    """Second avis independant : refait chaque exercice et compare au corrige."""
    exos = [
        {"index": i, "enonce": x.enonce, "corrige": x.corrige}
        for i, x in enumerate(data.exercices)
    ]
    prompt = (
        f"Matière : {lesson['matiere']}, niveau {lesson['niveau']}. Pour chaque "
        "exercice ci-dessous, résous-le toi-même entièrement AVANT de lire le "
        "corrigé proposé, puis indique si le corrigé est juste (calculs, "
        "résultat final, unités, raisonnement). Une seule erreur de calcul ou un "
        "résultat faux = correct: false, avec une remarque courte.\n\n"
        + json.dumps(exos, ensure_ascii=False, indent=2)
    )
    response = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        output_config={"effort": "high"},
        messages=[{"role": "user", "content": prompt}],
        output_format=Verification,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        return None
    faux = {v.index for v in response.parsed_output.verdicts if not v.correct}
    for v in response.parsed_output.verdicts:
        if not v.correct:
            print(f"    exercice {v.index} rejete : {v.remarque}")
    data.exercices = [x for i, x in enumerate(data.exercices) if i not in faux]
    return data if len(data.exercices) >= 2 else None


def main() -> int:
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        manifest = json.load(f)
    done = _done_slugs()
    todo = [m for m in manifest if m["slug"] not in done and (not MATIERE or m["matiere"] == MATIERE)]
    if LIMIT:
        todo = todo[:LIMIT]
    print(f"{len(todo)} lecon(s) a enrichir avec {MODEL}")

    out = {"_doc": "Complements generes par IA (generate_enrichments_ai.py), verifies par un second appel. A relire.",
           "topics": {}, "map": {}}
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, encoding="utf-8") as f:
            out = json.load(f)

    for n, meta in enumerate(todo, 1):
        slug = meta["slug"]
        print(f"[{n}/{len(todo)}] {slug}")
        with open(os.path.join(LESSONS_DIR, f"{slug}.json"), encoding="utf-8") as f:
            lesson = json.load(f)
        try:
            data = generate(lesson)
            data = verify(lesson, data) if data else None
        except anthropic.APIStatusError as e:
            print(f"    erreur API {e.status_code} : {e.message} - lecon ignoree")
            continue
        except anthropic.APIConnectionError:
            print("    erreur reseau - lecon ignoree (relancer plus tard)")
            continue
        if data is None:
            print("    rejetee (refus ou trop d'exercices faux)")
            continue
        topic = data.model_dump()
        errs = validate_enrichment(slug, topic)
        if errs:
            print("    structure invalide :", errs)
            continue
        out["topics"][slug] = topic
        out["map"][slug] = slug
        # Sauvegarde apres chaque lecon : le script est resumable.
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
            f.write("\n")
    print("Termine. Lance maintenant : python build_enrichments.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
