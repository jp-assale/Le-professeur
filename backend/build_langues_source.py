"""Ajoute a cours_seed/curriculum_source.json les chapitres OFFICIELS de Francais / Anglais / Allemand /
Espagnol (Cote d'Ivoire : DPFC ; Burkina Faso : guide de l'enseignant d'anglais 6e-5e), extraits par
extract_chapters_ai.py. Chaque titre a deja ete verifie mot pour mot dans le texte officiel ; les listes
de themes d'Allemand ci-dessous, recopiees a la main, sont re-verifiees ici de la meme facon.

Les entrees ajoutees portent "generateur": "langues" : generate_cours_content.py les ignore, elles sont
traitees par generate_cours_langues.py (consignes propres aux langues + verification).

Usage : python build_langues_source.py <dossier_ci> <dossier_bf>
"""
import difflib
import json
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(ROOT, "cours_seed", "curriculum_source.json")
CLASSES = ["6e", "5e", "4e", "3e", "2nde", "1ere", "Tle"]
LABEL = {"6e": "6e", "5e": "5e", "4e": "4e", "3e": "3e", "2nde": "2nde", "1ere": "1ère", "Tle": "Tle"}
NIVEAU = {"6e": "college", "5e": "college", "4e": "college", "3e": "college", "2nde": "lycee", "1ere": "lycee", "Tle": "lycee"}
EXAMEN = {"college": "BEPC", "lycee": "Baccalaureat"}
TYPOS = {"téléhphone": "téléphone"}


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "", s)


def clean(s):
    s = re.sub(r"\s*\{\s*", " à ", s)          # « { » = « à » mal lu dans le PDF
    s = s.replace("’", "'").strip(" .;:")
    for bad, good in TYPOS.items():
        s = s.replace(bad, good)
    s = re.sub(r"\s+", " ", s)
    if s.isupper() and len(s) > 3:               # TITRE EN MAJUSCULES -> Titre en minuscules
        s = s.capitalize()
    return s[:1].upper() + s[1:]


# Allemand : themes/lecons officiels recopies (la source est peu structuree). (classe, titre, theme_ou_note, doc)
ALLEMAND = {
    "4e": [
        ("WILLKOMMEN IN AFRIKA", "Bienvenue en Afrique — Leçon 1 : premiers contacts (civilités)"),
        ("IN DER SCHULE", "L'école — Leçon 2 : l'emploi du temps et les activités de classes"),
        ("HERZLICHEN GLÜCKWUNSCH", "unité de la progression annuelle"),
        ("PROBIER MAL", "unité de la progression annuelle"),
        ("GUTE BESSERUNG", "unité de la progression annuelle"),
        ("BESUCH IM DORF", "unité de la progression annuelle"),
        ("UNSER DEUTSCHCLUB", "unité de la progression annuelle"),
        ("SCHÖNES WOCHENENDE", "unité de la progression annuelle"),
    ],
    "3e": [
        ("les préparatifs d'un voyage", "Thème : les voyages — Leçon 1"),
        ("Un séjour dans une famille allemande", "Thème : la famille — Leçon 2"),
        ("JUGENDLICHE IN DEUTSCHLAND", "unité de la progression annuelle"),
        ("AUF NACH KÖLN", "unité de la progression annuelle"),
        ("AFRIKA IN DEUTSCHLAND", "unité de la progression annuelle"),
        ("BESUCH IN BERLIN", "unité de la progression annuelle"),
    ],
    "2nde": [(t, "thème au programme") for t in [
        "école et formation", "maison, foyer et vie en famille", "jeunesse", "monde du travail et métiers", "sport",
        "santé et bien-être", "congés, loisirs et voyages", "culture, arts et médias", "société de consommation", "environnement"]],
    "1ere": [(t, "thème au programme") for t in [
        "école et formation", "maison, foyer et vie en famille", "jeunesse", "monde du travail et métiers", "sport",
        "santé et bien-être", "congés, loisirs et voyages", "culture, arts et médias", "société de consommation", "environnement"]],
    "Tle": [(t, "thème au programme") for t in [
        "L'environnement et sa sauvegarde", "L'engagement de la jeunesse", "la résolution pacifique des conflits",
        "la consommation des stupéfiants et de l'alcool et leurs conséquences", "les problèmes liés à la jeunesse"]],
}
ALLEMAND_DOC = {  # classe -> (fichier texte, url)
}

FR_TAG = [("construction du sens", "lecture"), ("rédaction", "rédaction"), ("énoncés oraux", "oral"),
          ("outils grammaticaux", "grammaire"), ("orthographe", "orthographe")]


def tag_for(theme):
    low = theme.lower()
    return next((t for k, t in FR_TAG if k in low), "")


def main():
    ci_dir, bf_dir = sys.argv[1], sys.argv[2]
    ci = json.load(open(os.path.join(ci_dir, "chapitres_extraits.json"), encoding="utf-8"))
    bf = json.load(open(os.path.join(bf_dir, "chapitres_extraits.json"), encoding="utf-8"))
    ci_manifest = {(d["matiere"], d["classe"]): d for d in json.load(open(os.path.join(ci_dir, "_manifest.json"), encoding="utf-8"))}
    source = json.load(open(SOURCE, encoding="utf-8"))
    # on repart d'une source SANS les entrees deja ajoutees par ce script (relancable)
    source = [e for e in source if e.get("generateur") != "langues"]
    existing_titles = {}
    for e in source:
        existing_titles.setdefault((e["pays"], e["niveau"], e["matiere"]), []).extend(e["chapitres"])

    entries = {}   # (pays, niveau, matiere) -> entry

    def add(pays, matiere, classe, titre, theme, contenus, url, programme):
        """`classe` : un code (« 6e ») ou un groupe de classes partageant le meme programme officiel
        (« 6e-5e », « 2nde-1ere-Tle ») -> etiquette « 6e–5e », « 2nde–1ère–Tle »."""
        codes = classe.split("-")
        label = "–".join(LABEL[c] for c in codes)
        niveau = NIVEAU[codes[0]]
        key = (pays, niveau, matiere)
        entry = entries.setdefault(key, {
            "pays": pays, "niveau": niveau, "examen": EXAMEN[niveau], "matiere": matiere, "serie": None,
            "generateur": "langues", "chapitres": [], "details": {}, "sources_programmes": {},
        })
        chapitre = "%s · %s" % (label, titre)
        if chapitre in entry["details"]:
            return False
        entry["chapitres"].append(chapitre)
        entry["details"][chapitre] = {"classe": label, "titre_officiel": titre, "theme": theme,
                                      "contenus": contenus, "source_url": url}
        entry["sources_programmes"][label] = {"programme": programme, "url": url}
        return True

    skipped_dups = []
    # --- Cote d'Ivoire : Anglais, Espagnol, Francais (extraction verifiee) ---
    # Classes qui partagent EXACTEMENT le meme programme officiel (verifie : memes themes et titres) :
    # on ecrit une seule lecon pour le groupe (Anglais 6e-5e et 4e-3e, Espagnol 4e-3e et 2nde-1ere-Tle).
    GROUPS = {
        "Anglais": [("6e", "5e"), ("4e", "3e"), ("2nde",), ("1ere",), ("Tle",)],
        "Espagnol": [("4e", "3e"), ("2nde", "1ere", "Tle")],
        "Francais": [(c,) for c in CLASSES],
    }
    for matiere, groups in GROUPS.items():
        for group in groups:
            # fusion des classes du groupe : lecons uniques (titre normalise), contenus reunis
            merged_themes, index = [], {}
            for classe in group:
                doc = ci.get("%s|%s" % (matiere, classe))
                if not doc:
                    continue
                for th in doc["themes"]:
                    out_lecons = []
                    for lc in th["lecons"]:
                        k = norm(clean(lc["titre"]))
                        if k in index:
                            known = index[k]
                            for c in lc["contenus"]:
                                if norm(clean(c)) not in {norm(x) for x in known["contenus"]}:
                                    known["contenus"].append(clean(c))
                            continue
                        item = {"titre": lc["titre"], "contenus": [clean(c) for c in lc["contenus"]]}
                        index[k] = item
                        out_lecons.append(item)
                    if out_lecons:
                        merged_themes.append({"theme": th["theme"], "lecons": out_lecons})
            if not merged_themes:
                continue
            classe = "-".join(group)
            doc = {"themes": merged_themes}
            seen = {}
            for th in doc["themes"]:
                for lc in th["lecons"]:
                    seen.setdefault(norm(clean(lc["titre"])), []).append((th, lc))
            for th in doc["themes"]:
                for lc in th["lecons"]:
                    titre = clean(lc["titre"])
                    titre = re.sub(r"^(le[cç]on|lesson)\s*\d*\s*[:\-–]\s*", "", titre, flags=re.I)
                    titre = titre[:1].upper() + titre[1:]
                    if matiere == "Francais" and len(seen[norm(clean(lc["titre"]))]) > 1:
                        tag = tag_for(th["theme"])
                        if tag:
                            titre = "%s (%s)" % (titre, tag)
                    contenus = [clean(c) for c in lc["contenus"]][:10]
                    theme = clean(th["theme"])
                    niveau = NIVEAU[group[0]]
                    # Francais lycee CI / deja couvert par le livret : on n'ajoute que le nouveau
                    if matiere == "Francais" and niveau == "lycee":
                        old = existing_titles.get(("cote_ivoire", "lycee", "Francais"), [])
                        if any(difflib.SequenceMatcher(None, norm(titre), norm(o)).ratio() >= 0.8 or norm(o) in norm(titre) or norm(titre) in norm(o) for o in old):
                            skipped_dups.append("%s %s" % (classe, titre))
                            continue
                    d = ci_manifest[(matiere, group[0])]
                    add("cote_ivoire", matiere, classe, titre, theme, contenus, d["url"],
                        "Programme éducatif officiel (MENET/DPFC, Côte d'Ivoire) — %s, %s" % (matiere, "–".join(LABEL[c] for c in group)))

    # --- Cote d'Ivoire : Allemand (listes officielles recopiees, re-verifiees) ---
    for classe, items in ALLEMAND.items():
        d = ci_manifest[("Allemand", classe)]
        text = norm(open(os.path.join(ci_dir, d["fichier"]), encoding="utf-8").read())
        for titre, theme in items:
            if norm(titre.split(" — ")[0]) not in text:
                print("ECHEC GROUNDING Allemand", classe, titre)
                continue
            contenus = []
            if classe == "4e" and titre in ("WILLKOMMEN IN AFRIKA", "IN DER SCHULE"):
                src = ci["Allemand|4e"]["themes"]
                idx = 0 if titre == "WILLKOMMEN IN AFRIKA" else 1
                contenus = [clean(c) for c in src[idx]["lecons"][0]["contenus"]]
            if classe == "3e" and titre in ("les préparatifs d'un voyage", "Un séjour dans une famille allemande"):
                src = ci["Allemand|3e"]["themes"]
                for th in src:
                    for lc in th["lecons"]:
                        if norm(titre) in norm(lc["titre"]):
                            contenus = [clean(c) for c in lc["contenus"]]
            shown = clean(titre) if titre.isupper() else (titre[:1].upper() + titre[1:])
            if shown.isupper() or titre.isupper():
                shown = " ".join(w.capitalize() for w in titre.replace("!", "").split())
            add("cote_ivoire", "Allemand", classe, shown, theme, contenus, d["url"],
                "Programme éducatif officiel (MENET/DPFC, Côte d'Ivoire) — Allemand, %s" % LABEL[classe])

    # --- Burkina Faso : Anglais 6e et 5e (guide officiel MENAPLN) ---
    for classe in ("6e", "5e"):
        doc = bf.get("Anglais|%s" % classe)
        for th in (doc or {"themes": []})["themes"]:
            for lc in th["lecons"]:
                add("burkina_faso", "Anglais", classe, clean(lc["titre"]), "unité du guide officiel", [], doc["source_url"],
                    "Guide de l'enseignant d'anglais 6e-5e (MENAPLN, Burkina Faso) — %s" % LABEL[classe])

    new_entries = list(entries.values())
    for e in new_entries:
        e["source"] = "; ".join("%s : %s <%s>" % (k, v["programme"], v["url"]) for k, v in e["sources_programmes"].items())
        print("%-13s %-8s %-9s %3d chapitres" % (e["pays"], e["niveau"], e["matiere"], len(e["chapitres"])))
    print("TOTAL nouveaux chapitres :", sum(len(e["chapitres"]) for e in new_entries))
    print("Doublons Francais lycee ecartes :", len(skipped_dups), skipped_dups[:6])

    backup = SOURCE + ".bak"
    if not os.path.exists(backup):
        json.dump(json.load(open(SOURCE, encoding="utf-8")), open(backup, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(source + new_entries, open(SOURCE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("ecrit :", SOURCE)


if __name__ == "__main__":
    main()
