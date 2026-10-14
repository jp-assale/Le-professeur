"""Genere les lecons « Cours » de Francais / Anglais / Allemand / Espagnol a partir des chapitres OFFICIELS
ajoutes par build_langues_source.py (entrees de curriculum_source.json portant "generateur": "langues").

Pour chaque chapitre :
  1. generation de la lecon (memes champs que les autres lecons : intro, resume, concept, example, quiz),
     avec des consignes propres aux langues (explications en francais, exemples dans la langue etudiee avec
     traduction, niveau adapte a la classe) ;
  2. validation de structure (1 seule bonne reponse au quiz, 3 points de resume, pas de trace d'hesitation...) ;
  3. VERIFICATION par un second appel independant : justesse de la langue etrangere (orthographe, accents,
     grammaire, traductions), coherence avec le chapitre, quiz sans ambiguite. Le verificateur renvoie
     « ok », « corrige » (avec la lecon corrigee, re-validee ensuite) ou « rejete » (la lecon n'est pas gardee).
Resumable : relance-le, il saute les lecons deja presentes dans cours_seed/manifest.json.

Variables : LANGUES_GEN_MODEL, LANGUES_VERIFY_MODEL (defaut claude-sonnet-5-5), LANGUES_LIMIT (nb max de
nouvelles lecons), LANGUES_PER_GROUP=1 (lot pilote : 1 lecon par pays/niveau/matiere), LANGUES_MATIERE,
LANGUES_PAYS, LANGUES_WORKERS (defaut 4).

Usage : python generate_cours_langues.py
"""
import hashlib
import json
import os
import re
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from typing import List, Literal, Optional

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

from curriculum import contexte_pays_note, niveau_label, pays_avec_preposition

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

SEED_DIR = os.path.join(os.path.dirname(__file__), "cours_seed")
SOURCE_PATH = os.path.join(SEED_DIR, "curriculum_source.json")
LESSONS_DIR = os.path.join(SEED_DIR, "lessons")
MANIFEST_PATH = os.path.join(SEED_DIR, "manifest.json")
REPORT_PATH = os.path.join(SEED_DIR, "langues_report.json")
os.makedirs(LESSONS_DIR, exist_ok=True)

GEN_MODEL = os.environ.get("LANGUES_GEN_MODEL", "claude-sonnet-5-5")
VERIFY_MODEL = os.environ.get("LANGUES_VERIFY_MODEL", "claude-sonnet-5-5")
LIMIT = int(os.environ.get("LANGUES_LIMIT", "0")) or None
PER_GROUP = int(os.environ.get("LANGUES_PER_GROUP", "0")) or None
ONLY_MATIERE = os.environ.get("LANGUES_MATIERE") or None
ONLY_PAYS = os.environ.get("LANGUES_PAYS") or None
WORKERS = int(os.environ.get("LANGUES_WORKERS", "4"))

client = anthropic.Anthropic()
_lock = threading.Lock()
usage = {"in": 0, "out": 0}


# ----------------------------------------------------------------- modeles de sortie
class Point(BaseModel):
    icon: str
    text: str


class Resume(BaseModel):
    points: List[Point]


class Intro(BaseModel):
    heading: str
    body: str


class Concept(BaseModel):
    heading: str
    explanation: str
    highlight: str


class Example(BaseModel):
    problem: str
    steps: List[str]


class Choice(BaseModel):
    label: str
    correct: bool


class Quiz(BaseModel):
    question: str
    reponse_calculee: str
    choices: List[Choice]
    feedback_correct: str
    feedback_wrong: str


class LessonContent(BaseModel):
    title: str
    intro: Intro
    resume: Resume
    concept: Concept
    example: Example
    quiz: Quiz


class Verdict(BaseModel):
    statut: Literal["ok", "corrige", "rejete"]
    remarques: List[str]
    lecon_corrigee: Optional[LessonContent] = None


# ----------------------------------------------------------------- outils
def slugify(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "-", norm).strip("-").lower()[:60]


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "", s)


LANGUES = {"Anglais": "anglais", "Allemand": "allemand", "Espagnol": "espagnol"}
NIVEAU_CECRL = {  # repere de difficulte pour le prompt (jamais annonce a l'eleve)
    "6e": "A1 (debutant : phrases tres courtes, vocabulaire du quotidien)",
    "5e": "A1 (debutant : phrases tres courtes, vocabulaire du quotidien)",
    "4e": "A1 a A2 (phrases simples, vocabulaire courant)",
    "3e": "A2 (phrases simples a un peu plus longues)",
    "2nde": "A2 (communication simple mais plus autonome)",
    "1ère": "A2-B1 (textes courts, opinions simples)",
    "Tle": "B1 (textes plus riches, argumentation simple)",
}
BANNED = re.compile(r"\b(attends|recalcul\w*|hmm|en fait|erreur dans|devrait être|correction nécessaire|la réponse affichée)\b", re.I)
UNACCENTED = re.compile(r"\b(ecole|eleves?|etapes?|francais|systeme|reponses?|exemple\s+ci-dessus|probleme|regle|verifi\w*|generalement|different\w*|presenter|resume)\b", re.I)

SYSTEM = (
    "Tu es Le Prof JPA, un professeur de collège et de lycée d'Afrique de l'Ouest francophone. Tu rédiges en "
    "français correct, accentué et bien orthographié, pour des élèves, avec des exemples concrets du quotidien "
    "ouest-africain (prénoms locaux, marché, école, FCFA...). Quand la matière est une langue étrangère, tu "
    "n'écris QUE des phrases dont tu es parfaitement sûr : un seul mot faux enseigne une erreur à l'élève."
)


def build_prompt(entry: dict, chapitre: str, d: dict) -> str:
    matiere = entry["matiere"]
    classe = d["classe"]
    contenus = d.get("contenus") or []
    niveau = niveau_label(entry["pays"], entry["niveau"])
    langue = LANGUES.get(matiere)
    head = (
        f"Prépare une leçon animée pour un(e) élève de {classe} ({niveau}) en {matiere}, "
        f"{pays_avec_preposition(entry['pays'])}.\n"
        f"{contexte_pays_note(entry['pays'], entry['niveau'])}\n\n"
        f"Le chapitre EXACT du programme officiel à couvrir est : « {d['titre_officiel']} »\n"
        f"(thème du programme : {d['theme']})\n"
    )
    if contenus:
        head += "Notions que le programme officiel demande de traiter pour ce chapitre :\n" + "\n".join(
            f"- {c}" for c in contenus) + "\n"
    head += (
        "Reste strictement sur ce chapitre. N'invente aucun autre thème et ne cite jamais de manuel scolaire.\n\n"
    )

    if langue:
        regles = (
            f"RÈGLES POUR UNE LANGUE ÉTRANGÈRE ({langue}) :\n"
            f"- Niveau de difficulté visé (repère interne, ne le mentionne pas) : {NIVEAU_CECRL.get(classe, 'A2')}.\n"
            f"- Les explications sont en FRANÇAIS. Les mots, expressions et phrases en {langue} sont donnés avec leur "
            "traduction française (entre parenthèses).\n"
            f"- Orthographe, accents ({'ä ö ü ß' if langue == 'allemand' else 'ñ á é í ó ú ¿ ¡' if langue == 'espagnol' else 'apostrophes, majuscules'}), "
            "genres, accords, conjugaisons et traductions doivent être EXACTS. Phrases courtes et simples ; pas d'argot, "
            "pas d'expression dont tu n'es pas certain.\n"
            "- Si le titre officiel est le nom d'une unité sans explication (ex. en allemand), traite la situation de "
            "communication qu'il évoque de façon simple et générale, sans prétendre décrire un manuel précis.\n"
            "- concept.highlight : la règle ou le modèle de phrase clé, très court, avec un exemple et sa traduction.\n"
            "- example : un exercice guidé (traduire, compléter ou construire une phrase) : 'problem' = la consigne, "
            "'steps' = 4 à 6 étapes courtes qui montrent le raisonnement, la DERNIÈRE étape donne la réponse complète "
            f"en {langue} avec sa traduction.\n"
            f"- quiz : une question à choix multiples sur le point central, avec 4 options dont UNE SEULE correcte ; les "
            f"options fausses doivent être clairement fausses (pas deux réponses défendables).\n"
        )
    else:
        regles = (
            "RÈGLES POUR LE FRANÇAIS :\n"
            "- Explications claires en français ; donne la définition, une règle simple et des exemples courts.\n"
            "- Les exemples sont des phrases ou petits textes INVENTÉS (contexte africain), jamais de longs extraits "
            "d'œuvres ; si le chapitre porte sur une œuvre, une forme de texte ou une technique d'expression, explique "
            "la méthode sans citer de passages protégés.\n"
            "- example : une application guidée de la notion (analyser ou produire 1 à 2 phrases ou un court texte), en "
            "4 à 6 étapes courtes ; PAS de calcul chiffré.\n"
            "- quiz : une question à choix multiples qui vérifie la notion, 4 options dont UNE SEULE correcte, sans "
            "ambiguïté possible.\n"
        )

    structure = (
        "STRUCTURE (champs JSON) :\n"
        "- title : titre court de la leçon.\n"
        "- intro : heading + body = mise en situation vivante en 3 ou 4 phrases (français).\n"
        "- resume.points : EXACTEMENT 3 points d'au plus 12 mots, chacun avec UN SEUL emoji pertinent dans 'icon'.\n"
        "- concept : heading, explanation (4 à 8 phrases claires), highlight.\n"
        "- example : problem + steps.\n"
        "- quiz : question, reponse_calculee (la bonne réponse, recopiée à l'identique dans le libellé de la bonne "
        "option), choices (4), feedback_correct, feedback_wrong (explications propres et définitives).\n"
        "Consignes générales : tutoie l'élève, reste simple et concret, jamais infantilisant. N'écris JAMAIS de trace "
        "d'hésitation ('attends', 'en fait', 'recalculons'...). Pas de markdown, pas de HTML, pas de LaTeX. "
        "N'invente ni statistique, ni date, ni fait attribué à un événement ou un lieu réel.\n"
    )
    return head + regles + "\n" + structure


def validate(lesson: LessonContent, entry: dict, chapitre: str = "") -> list:
    """Retourne la liste des problemes de structure (vide = valide)."""
    errs = []
    q = lesson.quiz
    if len(q.choices) != 4:
        errs.append("le quiz n'a pas 4 options")
    if sum(1 for c in q.choices if c.correct) != 1:
        errs.append("le quiz n'a pas exactement 1 bonne option")
    else:
        good = next(c for c in q.choices if c.correct)
        if norm(good.label) != norm(q.reponse_calculee) and norm(q.reponse_calculee) not in norm(good.label):
            errs.append("reponse_calculee ne correspond pas a l'option correcte")
    if len({norm(c.label) for c in q.choices}) != len(q.choices):
        errs.append("options du quiz en double")
    if len(lesson.resume.points) != 3 or any(not p.icon.strip() or len(p.icon) > 8 or not p.text.strip() for p in lesson.resume.points):
        errs.append("resume : 3 points avec emoji requis")
    if not 3 <= len(lesson.example.steps) <= 8 or any(not s.strip() for s in lesson.example.steps):
        errs.append("example : 3 a 8 etapes non vides")
    if len(lesson.intro.body) < 60 or len(lesson.concept.explanation) < 120:
        errs.append("intro ou explication trop courte")
    blob = " ".join([lesson.intro.body, lesson.concept.explanation, lesson.concept.highlight, lesson.example.problem,
                     *lesson.example.steps, q.question, q.feedback_correct, q.feedback_wrong, *[p.text for p in lesson.resume.points]])
    if BANNED.search(q.feedback_correct + " " + q.feedback_wrong):
        errs.append("trace d'hesitation dans les feedbacks")
    if "**" in blob or "```" in blob or "\\(" in blob or "$" in blob:
        errs.append("markdown / LaTeX interdit")
    if UNACCENTED.search(blob) and "orthograph" not in chapitre.lower():  # une leçon d'orthographe montre des mots mal écrits
        errs.append("mot francais sans accent : " + UNACCENTED.search(blob).group(0))
    return errs


def call_generate(prompt: str) -> LessonContent:
    r = client.messages.parse(model=GEN_MODEL, max_tokens=7000, system=SYSTEM,
                              messages=[{"role": "user", "content": prompt}], output_format=LessonContent)
    with _lock:
        usage["in"] += r.usage.input_tokens
        usage["out"] += r.usage.output_tokens
    if r.parsed_output is None:
        raise RuntimeError("sortie vide (%s)" % r.stop_reason)
    return r.parsed_output


def call_verify(entry: dict, d: dict, lesson: LessonContent) -> Verdict:
    matiere = entry["matiere"]
    langue = LANGUES.get(matiere)
    prompt = (
        f"Tu es un relecteur exigeant ({'professeur natif/agrégé de ' + langue if langue else 'professeur de français'}). "
        f"Voici une leçon de {matiere} pour la classe de {d['classe']} sur le chapitre officiel « {d['titre_officiel']} »"
        f" (thème : {d['theme']}).\n\n"
        "Relis TOUT, mot à mot, et vérifie :\n"
        + ("1. Chaque mot, phrase et traduction dans la langue étudiée : orthographe, accents, genre, accords, "
           "conjugaison, ordre des mots, sens exact de la traduction française.\n" if langue else
           "1. L'exactitude des règles, définitions et exemples de français (orthographe, grammaire, terminologie).\n")
        + "2. Le quiz : exactement UNE option correcte, 'reponse_calculee' identique à cette option, les trois autres "
        "clairement fausses (aucune ambiguïté), feedbacks cohérents.\n"
        "3. La cohérence avec le chapitre demandé (pas de hors-sujet) et aucune affirmation factuelle inventée.\n"
        "4. Le niveau : adapté à la classe, sans formulation trop avancée.\n\n"
        "Réponds :\n"
        "- statut 'ok' si tout est exact ;\n"
        "- statut 'corrige' si tu as trouvé des erreurs réparables : fournis alors 'lecon_corrigee' (la leçon COMPLÈTE "
        "corrigée, mêmes champs) et liste les corrections dans 'remarques' ;\n"
        "- statut 'rejete' si la leçon est trop fausse ou hors-sujet pour être réparée.\n"
        "Sois sévère : en cas de doute sur une phrase de la langue étudiée, corrige-la ou remplace-la par une phrase sûre.\n\n"
        + json.dumps(lesson.model_dump(), ensure_ascii=False, indent=1)
    )
    r = client.messages.parse(model=VERIFY_MODEL, max_tokens=9000,
                              messages=[{"role": "user", "content": prompt}], output_format=Verdict)
    with _lock:
        usage["in"] += r.usage.input_tokens
        usage["out"] += r.usage.output_tokens
    if r.parsed_output is None:
        raise RuntimeError("verification vide (%s)" % r.stop_reason)
    return r.parsed_output


def process(task: dict, manifest: list, slugs: dict, report: dict):
    entry, chapitre, d = task["entry"], task["chapitre"], task["details"]
    base = f"{entry['pays']}-{entry['niveau']}-{entry['matiere']}--{chapitre}"
    with _lock:
        slug = slugify(base)
        if slug in slugs:
            if slugs[slug] == chapitre:
                return "deja"
            slug = f"{slug[:53]}-{hashlib.md5(base.encode('utf-8')).hexdigest()[:6]}"
            if slug in slugs:
                return "deja"
    prompt = build_prompt(entry, chapitre, d)
    lesson = None
    last_errs = []
    for attempt in (1, 2):
        try:
            cand = call_generate(prompt if attempt == 1 else prompt + "\n\nATTENTION, ta tentative précédente était invalide : " + "; ".join(last_errs))
        except Exception as exc:
            last_errs = [str(exc)[:200]]
            continue
        last_errs = validate(cand, entry, chapitre)
        if not last_errs:
            lesson = cand
            break
    if lesson is None:
        with _lock:
            report["echecs"].append({"slug": slug, "chapitre": chapitre, "raison": last_errs})
        return "echec"

    try:
        verdict = call_verify(entry, d, lesson)
    except Exception as exc:
        with _lock:
            report["echecs"].append({"slug": slug, "chapitre": chapitre, "raison": ["verification : " + str(exc)[:150]]})
        return "echec"
    status = verdict.statut
    if status == "rejete":
        with _lock:
            report["rejetes"].append({"slug": slug, "chapitre": chapitre, "remarques": verdict.remarques})
        return "rejete"
    if status == "corrige":
        fixed = verdict.lecon_corrigee
        errs = validate(fixed, entry, chapitre) if fixed else ["pas de lecon corrigee"]
        if errs:
            with _lock:
                report["rejetes"].append({"slug": slug, "chapitre": chapitre, "remarques": verdict.remarques + ["correction invalide : " + "; ".join(errs)]})
            return "rejete"
        lesson = fixed

    content = lesson.model_dump()
    content["title"] = chapitre  # la liste de l'appli affiche le titre : on y met la classe (« 6e–5e · ... »)
    record = {
        "slug": slug, "pays": entry["pays"], "niveau": entry["niveau"], "examen": entry.get("examen", ""),
        "serie": entry.get("serie"), "matiere": entry["matiere"], "chapitre": chapitre, "classe": d["classe"],
        "source": entry.get("source", ""), "template": "text_only", **content,
        "verification": "corrige" if status == "corrige" else "ok",
    }
    with _lock:
        with open(os.path.join(LESSONS_DIR, f"{slug}.json"), "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        manifest.append({
            "slug": slug, "pays": entry["pays"], "niveau": entry["niveau"], "examen": entry.get("examen", ""),
            "serie": entry.get("serie"), "matiere": entry["matiere"], "chapitre": chapitre, "template": "text_only",
            "title": chapitre,
        })
        slugs[slug] = chapitre
        with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        report["generees"].append({"slug": slug, "statut": status, "remarques": verdict.remarques})
    return status


def main():
    source = [e for e in json.load(open(SOURCE_PATH, encoding="utf-8")) if e.get("generateur") == "langues"]
    manifest = json.load(open(MANIFEST_PATH, encoding="utf-8")) if os.path.exists(MANIFEST_PATH) else []
    slugs = {m["slug"]: m["chapitre"] for m in manifest}
    report = json.load(open(REPORT_PATH, encoding="utf-8")) if os.path.exists(REPORT_PATH) else {}
    report.setdefault("generees", [])
    report.setdefault("rejetes", [])
    report["echecs"] = []

    tasks = []
    for entry in source:
        if (ONLY_MATIERE and entry["matiere"] != ONLY_MATIERE) or (ONLY_PAYS and entry["pays"] != ONLY_PAYS):
            continue
        count = 0
        for chapitre in entry["chapitres"]:
            if PER_GROUP and count >= PER_GROUP:
                break
            base = f"{entry['pays']}-{entry['niveau']}-{entry['matiere']}--{chapitre}"
            if slugify(base) in slugs:
                continue
            tasks.append({"entry": entry, "chapitre": chapitre, "details": entry["details"][chapitre]})
            count += 1
    if LIMIT:
        tasks = tasks[:LIMIT]
    print(f"{len(tasks)} lecon(s) a generer avec {GEN_MODEL} (verification : {VERIFY_MODEL}), {WORKERS} en parallele.", flush=True)

    counts = {}

    def run(t):
        try:
            res = process(t, manifest, slugs, report)
        except Exception as exc:  # une lecon en erreur ne doit pas arreter le lot
            res = "erreur"
            with _lock:
                report["echecs"].append({"chapitre": t["chapitre"], "raison": [str(exc)[:200]]})
        with _lock:
            counts[res] = counts.get(res, 0) + 1
            print("  [%s] %s" % (res.upper(), t["chapitre"][:90]), flush=True)
        return res

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        list(pool.map(run, tasks))

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("\nBilan :", counts)
    print("Jetons : %d entree, %d sortie (cout indicatif a verifier sur la console Anthropic)" % (usage["in"], usage["out"]))


if __name__ == "__main__":
    main()
