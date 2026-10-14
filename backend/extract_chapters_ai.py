"""Extrait la liste des themes / lecons du CORPS DU PROGRAMME de chaque programme educatif OFFICIEL
(Cote d'Ivoire, DPFC) deja converti en texte par extract_programmes_ci.py.

Regle du projet (jamais de programme invente) : chaque titre retenu doit se retrouver MOT POUR MOT
(apres normalisation des accents, de la casse et de la ponctuation) dans le texte officiel ; sinon il est
rejete et signale. Les « contenus » (vocabulaire, grammaire, fonctions...) sont filtres de la meme facon.

Usage : python extract_chapters_ai.py <dossier_textes> <sortie.json> [Matiere] [classe]
"""
import json
import os
import re
import sys
import unicodedata
from typing import List

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
MODEL = os.environ.get("EXTRACT_MODEL", "claude-sonnet-5-5")
client = anthropic.Anthropic()


class Lecon(BaseModel):
    titre: str
    contenus: List[str]


class Theme(BaseModel):
    titre: str
    lecons: List[Lecon]


class Programme(BaseModel):
    classe_traitee: str
    themes: List[Theme]


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "", s)


CLASSES = {"6e": "sixième (6e)", "5e": "cinquième (5e)", "4e": "quatrième (4e)", "3e": "troisième (3e)",
           "2nde": "seconde (2nde)", "1ere": "première (1ère)", "Tle": "terminale (Tle)"}


def extract(matiere: str, classe: str, text: str, pays_label: str = "Côte d'Ivoire") -> Programme:
    prompt = (
        f"Voici le texte brut (extrait d'un PDF) d'un programme éducatif ou guide de l'enseignant OFFICIEL de "
        f"{matiere} du ministère de l'Éducation nationale du pays suivant : {pays_label}. Il peut couvrir plusieurs "
        f"classes et contient souvent, en plus du programme, des exemples de fiches de leçon à IGNORER.\n\n"
        f"Extrais la structure du CORPS DU PROGRAMME pour la classe de {CLASSES[classe]} UNIQUEMENT : la liste des "
        "thèmes (ou unités) et, pour chacun, la liste de ses leçons (ou, si le programme ne découpe pas en leçons, "
        "une seule leçon portant le titre du thème).\n"
        "Règles strictes :\n"
        "- Recopie les titres EXACTEMENT comme dans le document (même langue : anglais, allemand, espagnol ou "
        "français ; mêmes mots). N'invente, ne traduis, ne reformule rien.\n"
        "- Pour chaque leçon, 'contenus' = 3 à 8 notions courtes RECOPIÉES du tableau des contenus/habiletés "
        "(vocabulaire, grammaire, fonctions de communication, notions de langue, techniques d'expression...). Si la "
        "leçon n'a pas de contenus lisibles, liste vide.\n"
        "- Ignore le guide d'exécution, les progressions, les exemples de plans de leçon, les annexes, le profil de "
        "sortie, les autres classes.\n"
        "- Si cette classe n'est pas traitée dans le document, renvoie une liste de thèmes vide.\n"
        "- Mets dans 'classe_traitee' la classe que tu as réellement trouvée (par ex. « 6e », « Tle »).\n\n"
        "=== TEXTE DU PROGRAMME ===\n" + text
    )
    response = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
        output_format=Programme,
    )
    if response.parsed_output is None:
        raise RuntimeError("refus ou sortie vide (%s)" % response.stop_reason)
    return response.parsed_output


def ground(prog: Programme, text: str):
    """Garde uniquement ce qui est present dans le texte officiel. Retourne (liste_themes, rejets)."""
    haystack = norm(text)
    kept, rejected = [], []
    for th in prog.themes:
        if norm(th.titre) not in haystack:
            rejected.append("theme: " + th.titre)
            continue
        lecons = []
        for lc in th.lecons:
            if norm(lc.titre) not in haystack:
                rejected.append("lecon: " + lc.titre)
                continue
            contenus = [c.strip() for c in lc.contenus if c.strip() and norm(c) in haystack]
            dropped = len(lc.contenus) - len(contenus)
            if dropped:
                rejected.append("%d contenu(s) non retrouves dans: %s" % (dropped, lc.titre))
            lecons.append({"titre": lc.titre.strip(), "contenus": contenus})
        if lecons:
            kept.append({"theme": th.titre.strip(), "lecons": lecons})
    return kept, rejected


def main():
    src, out_path = sys.argv[1], sys.argv[2]
    only_m = sys.argv[3] if len(sys.argv) > 3 else None
    only_c = sys.argv[4] if len(sys.argv) > 4 else None
    manifest = json.load(open(os.path.join(src, "_manifest.json"), encoding="utf-8"))
    result = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else {}
    for doc in manifest:
        m, c = doc["matiere"], doc["classe"]
        if (only_m and m != only_m) or (only_c and c != only_c):
            continue
        key = "%s|%s" % (m, c)
        if key in result:
            print("deja fait :", key)
            continue
        text = open(os.path.join(src, doc["fichier"]), encoding="utf-8").read()
        print("%s %s : extraction (%d car.)..." % (m, c, len(text)), flush=True)
        try:
            prog = extract(m, c, text, doc.get("pays_label", "Côte d'Ivoire"))
        except Exception as exc:
            print("   ECHEC :", exc)
            continue
        themes, rejected = ground(prog, text)
        n_l = sum(len(t["lecons"]) for t in themes)
        print("   classe lue : %s | %d theme(s), %d lecon(s) retenus | %d rejet(s)" % (prog.classe_traitee, len(themes), n_l, len(rejected)))
        for r in rejected[:6]:
            print("     rejet :", r)
        result[key] = {"matiere": m, "classe": c, "classe_lue": prog.classe_traitee, "source_url": doc["url"],
                       "themes": themes, "rejets": rejected}
        json.dump(result, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
