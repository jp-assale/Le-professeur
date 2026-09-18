"""Ajoute le champ "resume" (3 points-cles + icone, pour l'animation sous la
mise en situation) aux lecons Cours deja generees qui ne l'ont pas encore.

Ne touche a AUCUN autre champ de la lecon (intro/concept/example/quiz
restent identiques, deja valides) - un seul petit appel IA par lecon,
base sur le contenu existant, pas une regeneration complete.

Resumable : relance-le, il saute les lecons qui ont deja un "resume".
Utilise COURS_GEN_LIMIT pour limiter le nombre de lecons traitees en un run.

Usage:
    python backfill_resume.py
    COURS_GEN_LIMIT=10 python backfill_resume.py
"""
import glob
import json
import os
import time

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

SEED_DIR = os.path.join(os.path.dirname(__file__), "cours_seed")
LESSONS_DIR = os.path.join(SEED_DIR, "lessons")

MODEL = os.environ.get("ASSISTANT_MODEL", "claude-haiku-4-5-20251001")
LIMIT = int(os.environ.get("COURS_GEN_LIMIT", "0")) or None

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def build_prompt(lesson: dict) -> str:
    return (
        "Voici la mise en situation et le concept d'une lecon scolaire deja "
        "validee :\n\n"
        f"Mise en situation : {lesson['intro']['body']}\n\n"
        f"Concept : {lesson['concept']['explanation']}\n\n"
        "Genere EXACTEMENT 3 points tres courts (une phrase de 12 mots "
        "maximum chacun) qui resument les idees-cles de ces deux textes, "
        "pour un rappel visuel rapide affiche juste apres la mise en "
        "situation. Chaque point a un unique emoji pertinent (jamais deux "
        "emojis colles, jamais de texte a la place de l'emoji). Reponds "
        "UNIQUEMENT avec un objet JSON valide, sans texte autour, sans "
        "balises markdown, exactement dans ce format :\n"
        '{"points": [{"icon": "emoji", "text": "..."}, '
        '{"icon": "emoji", "text": "..."}, {"icon": "emoji", "text": "..."}]}'
    )


def parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def main():
    paths = sorted(glob.glob(os.path.join(LESSONS_DIR, "*.json")))

    done = 0
    skipped = 0
    failed = []

    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            lesson = json.load(f)

        if "resume" in lesson:
            skipped += 1
            continue
        if LIMIT and done >= LIMIT:
            continue

        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=400,
                messages=[{"role": "user", "content": build_prompt(lesson)}],
            )
            raw = "".join(b.text for b in response.content if b.type == "text")
            resume = parse_json(raw)
        except Exception as exc:
            print(f"  [ECHEC] {lesson['slug']} : {exc}")
            failed.append(lesson["slug"])
            continue

        lesson["resume"] = resume
        with open(path, "w", encoding="utf-8") as f:
            json.dump(lesson, f, ensure_ascii=False, indent=2)

        done += 1
        print(f"  [OK] {lesson['slug']}")
        time.sleep(0.3)

    print(f"\nTermine. Traitees ce run : {done}. Deja a jour : {skipped}. "
          f"Echecs : {len(failed)}.")
    if failed:
        print("Slugs en echec (relancer le script les reprendra) :", failed)


if __name__ == "__main__":
    main()
