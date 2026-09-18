"""Genere le contenu des lecons "Cours" a partir de cours_seed/curriculum_source.json.

Chaque theme (pays/niveau/matiere/chapitre) confirme dans le livret devient une
lecon JSON dans cours_seed/lessons/<slug>.json, listee dans cours_seed/manifest.json.

Le script est resumable : relance-le, il saute les slugs deja generes. Utilise
COURS_GEN_LIMIT pour limiter le nombre de NOUVELLES lecons generees en un run
(utile pour un lot de validation avant de lancer la generation complete).

Usage:
    python generate_cours_content.py
    COURS_GEN_LIMIT=10 python generate_cours_content.py
"""
import json
import os
import re
import sys
import time
import unicodedata

from anthropic import Anthropic
from dotenv import load_dotenv

from curriculum import PAYS, niveau_label

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

SEED_DIR = os.path.join(os.path.dirname(__file__), "cours_seed")
SOURCE_PATH = os.path.join(SEED_DIR, "curriculum_source.json")
LESSONS_DIR = os.path.join(SEED_DIR, "lessons")
MANIFEST_PATH = os.path.join(SEED_DIR, "manifest.json")
os.makedirs(LESSONS_DIR, exist_ok=True)

MODEL = os.environ.get("ASSISTANT_MODEL", "claude-haiku-4-5-20251001")
LIMIT = int(os.environ.get("COURS_GEN_LIMIT", "0")) or None

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

PAYS_LABEL = {p["code"]: p["label"] for p in PAYS}


def slugify(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    norm = re.sub(r"[^a-zA-Z0-9]+", "-", norm).strip("-").lower()
    return norm[:60]


def classify_template(matiere: str, niveau: str, chapitre: str) -> str:
    low = chapitre.lower()
    if ("thalès" in low or "thales" in low) and "solide" not in low and "espace" not in low:
        return "geometry_ratio"
    if matiere == "Physique-Chimie" and "force" in low:
        return "physics_vector"
    if matiere == "Mathematiques" and niveau == "college" and "affine" in low:
        return "function_affine"
    return "text_only"


TEMPLATE_NOTE = {
    "geometry_ratio": (
        "Cette lecon inclut une simulation deja codee (un triangle ABC avec un "
        "point M sur [AB] et N sur [AC], l'eleve fait glisser M et voit les "
        "rapports AM/AB, AN/AC, MN/BC se recalculer, avec detection du "
        "parallelisme). Ne decris PAS cette simulation dans ton JSON, elle est "
        "ajoutee automatiquement entre 'concept' et 'example'. Concentre-toi sur "
        "une mise en situation, un enonce, un exemple chiffre et un quiz qui "
        "restent coherents avec cette simulation (rapports de Thales)."
    ),
    "physics_vector": (
        "Cette lecon inclut une simulation deja codee (un solide soumis a une "
        "force F1 fixe et une force F2 reglable en intensite et direction, "
        "l'eleve regle F2 pour equilibrer le solide, avec detection de "
        "l'equilibre). Ne decris PAS cette simulation dans ton JSON, elle est "
        "ajoutee automatiquement entre 'concept' et 'example'. Concentre-toi sur "
        "une mise en situation, un enonce, un exemple chiffre et un quiz "
        "coherents avec cette simulation (equilibre de deux forces)."
    ),
    "function_affine": (
        "Cette lecon inclut une simulation deja codee (un graphique interactif "
        "d'une fonction affine f(x) = a*x + b, avec des curseurs pour a et b, "
        "l'eleve voit la droite bouger en direct). Ne decris PAS cette "
        "simulation dans ton JSON, elle est ajoutee automatiquement entre "
        "'concept' et 'example'. Concentre-toi sur une mise en situation, un "
        "enonce, un exemple chiffre et un quiz coherents avec une fonction "
        "affine (de preference un contexte concret africain, prix en FCFA si "
        "pertinent)."
    ),
    "text_only": (
        "Cette lecon n'a pas de simulation interactive. Compense en rendant "
        "l'exemple tres concret et la mise en situation vivante."
    ),
}

JSON_SCHEMA_HINT = (
    '{"title": "...", '
    '"intro": {"heading": "...", "body": "..."}, '
    '"resume": {"points": [{"icon": "emoji unique", "text": "..."}, '
    '{"icon": "emoji unique", "text": "..."}, {"icon": "emoji unique", "text": "..."}]}, '
    '"concept": {"heading": "...", "explanation": "...", "highlight": "..."}, '
    '"example": {"problem": "...", "steps": ["...", "..."]}, '
    '"quiz": {"question": "...", '
    '"reponse_calculee": "<le resultat exact que TU calcules pour cette question, '
    'rempli AVANT choices - jamais montre a l\'eleve>", '
    '"choices": [{"label": "...", "correct": false}, {"label": "...", "correct": true}, '
    '{"label": "...", "correct": false}, {"label": "...", "correct": false}], '
    '"feedback_correct": "...", "feedback_wrong": "..."}}'
)


QUALITATIVE_MATIERES = {"Philosophie", "Histoire-Geographie", "Francais", "Anglais", "Allemand", "Espagnol"}


def build_prompt(entry: dict, chapitre: str, template: str) -> str:
    pays_label = PAYS_LABEL.get(entry["pays"], entry["pays"])
    niveau = niveau_label(entry["pays"], entry["niveau"])
    serie = entry.get("serie")
    examen_txt = entry.get("examen", "")
    if serie:
        examen_txt += f", série {serie}"

    if entry["matiere"] in QUALITATIVE_MATIERES:
        example_instruction = (
            "3. Exemple d'analyse : PAS de calcul chiffre. Applique le concept a "
            "un cas concret (un evenement, un texte, une situation, un "
            "raisonnement) etape par etape (4 a 6 etapes courtes), en menant un "
            "vrai raisonnement ou une vraie analyse.\n"
        )
        factual_guard = (
            "- N'invente JAMAIS de statistique, pourcentage, date precise ou "
            "chiffre presente comme un fait historique/reel, sauf s'il est "
            "largement etabli et verifiable (ex: une date d'independance "
            "connue). N'attribue jamais un chiffre invente a un evenement, un "
            "lieu ou un personnage reel. Si tu as besoin d'un exemple chiffre, "
            "utilise une situation clairement fictive et generique plutot "
            "qu'un evenement/lieu reel precis.\n"
        )
    else:
        example_instruction = (
            "3. Exemple resolu : un probleme chiffre concret, avec les etapes "
            "de resolution decomposees une par une (4 a 6 etapes courtes). Les "
            "valeurs numeriques peuvent etre inventees pour l'exercice (comme "
            "dans un enonce de manuel scolaire), mais ne les attribue jamais a "
            "un evenement/lieu/personnage reel precis comme si c'etait un fait "
            "reel.\n"
        )
        factual_guard = ""

    return (
        f"Tu es Le Prof JPA, un professeur qui prepare une lecon animee pour "
        f"un(e) eleve du {niveau} ({examen_txt}) en {entry['matiere']}, au "
        f"{pays_label}.\n\n"
        f"Le chapitre EXACT du programme officiel a couvrir est :\n"
        f"« {chapitre} »\n"
        f"(source du programme : {entry['source']})\n\n"
        "Reste strictement sur ce chapitre precis, n'invente aucun autre "
        "theme et ne deborde pas sur d'autres notions du programme.\n\n"
        f"{TEMPLATE_NOTE[template]}\n\n"
        "Structure la lecon en un diaporama de plusieurs slides :\n"
        "1. Mise en situation : une accroche concrete (contexte de vie "
        "courante en Afrique de l'Ouest si possible) qui introduit le "
        "chapitre, 3-4 phrases maximum.\n"
        "1bis. Resume en un coup d'oeil (champ 'resume') : EXACTEMENT 3 "
        "points tres courts (une phrase de 12 mots maximum chacun) qui "
        "resument les idees-cles de la mise en situation et du concept, "
        "pour un rappel visuel rapide juste apres la mise en situation. "
        "Chaque point a un unique emoji pertinent (jamais deux emojis "
        "colles, jamais de texte a la place de l'emoji).\n"
        "2. Concept : l'enonce ou la definition centrale du chapitre, clair "
        "et precis, avec une phrase de mise en contexte et une formule/regle "
        "cle isolee dans 'highlight' (courte, sans mise en forme).\n"
        f"{example_instruction}"
        "4. Question flash : une question a choix multiples (4 options, une "
        "seule correcte) qui verifie la comprehension du chapitre, avec un "
        "feedback different si bonne ou mauvaise reponse.\n\n"
        "Consignes :\n"
        "- Tutoie l'eleve, reste simple, concret, jamais infantilisant.\n"
        f"{factual_guard}"
        "- Pour la question flash en particulier : remplis D'ABORD le champ "
        "'reponse_calculee' avec le resultat que tu calcules pour cette "
        "question (resous-la entierement, deux fois si besoin, avec deux "
        "methodes ou deux ordres de calcul qui doivent tomber sur le meme "
        "resultat). Remplis 'choices' SEULEMENT APRES avoir fixe "
        "'reponse_calculee' : l'option dont le libelle correspond EXACTEMENT "
        "a 'reponse_calculee' (memes chiffres, memes unites) recoit "
        "correct=true, aucune autre. Ne reviens jamais sur 'reponse_calculee' "
        "ou sur 'choices' apres coup - s'ils ne concordent pas avec ce que tu "
        "ecris dans feedback_correct, c'est feedback_correct qui est en tort, "
        "pas l'inverse.\n"
        "- Le champ feedback_correct et feedback_wrong ne doivent contenir "
        "QUE l'explication propre et definitive, jamais de trace de "
        "verification ou d'hesitation visible pour l'eleve. Ces mots/tournures "
        "sont STRICTEMENT INTERDITS dans feedback_correct et feedback_wrong : "
        "'attends', 'recalcul', 'recalculons', 'hmm', 'en fait', 'erreur dans "
        "mon enonce', 'erreur dans le quiz', 'devrait etre', 'la reponse "
        "affichee dit', 'correction necessaire', ou toute phrase qui remet en "
        "question l'option marquee correct=true. Si tu ressens le besoin "
        "d'ecrire une de ces tournures, c'est que ton calcul initial etait "
        "faux : corrige silencieusement le champ 'choices' et n'ecris que le "
        "resultat final propre.\n"
        "- Pour toute formule (puissances, indices, fractions...), utilise la "
        "notation LaTeX entre signes dollar : $...$. Hors de ces $...$, "
        "n'utilise que du texte simple (pas de markdown, pas de balises "
        "HTML).\n"
        "- Reponds UNIQUEMENT avec un objet JSON valide, sans texte autour, "
        "sans balises markdown ```, exactement dans ce format :\n"
        f"{JSON_SCHEMA_HINT}"
    )


def parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def main():
    source = json.load(open(SOURCE_PATH, encoding="utf-8"))
    manifest = json.load(open(MANIFEST_PATH, encoding="utf-8")) if os.path.exists(MANIFEST_PATH) else []
    existing_slugs = {m["slug"]: m["chapitre"] for m in manifest}

    generated_this_run = 0
    skipped = 0
    failed = []

    for entry in source:
        for chapitre in entry["chapitres"]:
            serie_part = entry.get("serie", "")
            slug_base = f"{entry['pays']}-{entry['niveau']}-{entry['matiere']}-{serie_part}-{chapitre}"
            slug = slugify(slug_base)

            if slug in existing_slugs:
                if existing_slugs[slug] == chapitre:
                    skipped += 1
                    continue
                # Vrai conflit : deux chapitres differents se reduisent au meme
                # slug ASCII (ex: symboles mathematiques stripped). On desambiguise
                # avec un hash court plutot que d'ecraser silencieusement l'un des
                # deux themes.
                import hashlib
                h = hashlib.md5(slug_base.encode("utf-8")).hexdigest()[:6]
                slug = f"{slug[:53]}-{h}"
                if slug in existing_slugs:
                    skipped += 1
                    continue
            if LIMIT and generated_this_run >= LIMIT:
                continue

            template = classify_template(entry["matiere"], entry["niveau"], chapitre)
            prompt = build_prompt(entry, chapitre, template)

            try:
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=2600,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = "".join(b.text for b in response.content if b.type == "text")
                lesson_content = parse_json(raw)
            except Exception as exc:
                print(f"  [ECHEC] {slug} : {exc}")
                failed.append(slug)
                continue

            lesson = {
                "slug": slug,
                "pays": entry["pays"],
                "niveau": entry["niveau"],
                "examen": entry.get("examen", ""),
                "serie": entry.get("serie"),
                "matiere": entry["matiere"],
                "chapitre": chapitre,
                "source": entry["source"],
                "template": template,
                **lesson_content,
            }

            with open(os.path.join(LESSONS_DIR, f"{slug}.json"), "w", encoding="utf-8") as f:
                json.dump(lesson, f, ensure_ascii=False, indent=2)

            manifest.append({
                "slug": slug, "pays": entry["pays"], "niveau": entry["niveau"],
                "examen": entry.get("examen", ""), "serie": entry.get("serie"),
                "matiere": entry["matiere"], "chapitre": chapitre, "template": template,
                "title": lesson_content.get("title", chapitre),
            })
            existing_slugs[slug] = chapitre
            generated_this_run += 1
            print(f"  [OK] {slug} ({template})")

            with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)

            time.sleep(0.3)

    print(f"\nTermine. Generees ce run : {generated_this_run}. Deja existantes : {skipped}. "
          f"Echecs : {len(failed)}.")
    if failed:
        print("Slugs en echec (relancer le script les reprendra) :", failed)


if __name__ == "__main__":
    main()
