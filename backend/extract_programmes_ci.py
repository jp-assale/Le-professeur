"""Extrait le texte des programmes educatifs OFFICIELS de Cote d'Ivoire (DPFC, ministere de l'Education
nationale, https://dpfc-ci.net/?page_id=283) pour Francais, Anglais, Allemand, Espagnol.

Les PDF ont ete lus avec l'outil de lecture web (qui les met en cache localement). Ce script ne telecharge
rien : il lit ces copies locales et ecrit un fichier texte par document dans le dossier de travail.

Usage : python extract_programmes_ci.py <dossier_cache_pdf> <dossier_sortie>
"""
import json
import os
import re
import sys

from pypdf import PdfReader

BASE = "https://dpfc-ci.net/wp-content/uploads/"
DOCS = [
    # (matiere, classe, fichier cache, url source)
    ("Anglais", "6e", "webfetch-1791980433270-b2s5ip", "/dpfc_fichiers/Programmes/prg_secondaire/Anglais/ANGLAIS_6eme.pdf"),
    ("Anglais", "5e", "webfetch-1791980433857-b253ol", "/dpfc_fichiers/Programmes/prg_secondaire/Anglais/ANGLAIS_5eme.pdf"),
    ("Anglais", "4e", "webfetch-1791980434042-uabjhr", "/dpfc_fichiers/Programmes/prg_secondaire/Anglais/ANGLAIS_4eme.pdf"),
    ("Anglais", "3e", "webfetch-1791980435409-m9wg8u", "/dpfc_fichiers/Programmes/prg_secondaire/Anglais/ANGLAIS_3eme.pdf"),
    ("Anglais", "2nde", "webfetch-1791980433756-b15xz0", "dpfc_fichiers/Programmes/prg_secondaire/Anglais/ANGLAIS_PROGRAMME_EDUCATIF_SECONDE.pdf"),
    ("Anglais", "1ere", "webfetch-1791980434579-8yjv4m", "dpfc_fichiers/Programmes/prg_secondaire/Anglais/ANGLAIS_PROGRAMME_EDUCATIF_PREMIERE.pdf"),
    ("Anglais", "Tle", "webfetch-1791980435157-4nh79h", "dpfc_fichiers/Programmes/prg_secondaire/Anglais/ANGLAIS_PROGRAMME_EDUCATIF_TERMINALE.pdf"),
    ("Allemand", "4e", "webfetch-1791980448051-v86n5u", "/dpfc_fichiers/Programmes/prg_secondaire/Allemand/ALLEMAND_4eme.pdf"),
    ("Allemand", "3e", "webfetch-1791980446882-tt0so6", "/dpfc_fichiers/Programmes/prg_secondaire/Allemand/ALLEMAND_3eme.pdf"),
    ("Allemand", "2nde", "webfetch-1791980451705-ze6k23", "dpfc_fichiers/Programmes/prg_secondaire/Allemand/ALLEMAND_PROGRAMME_EDUCATIF_SECONDE.pdf"),
    ("Allemand", "1ere", "webfetch-1791980447851-lkkaft", "dpfc_fichiers/Programmes/prg_secondaire/Allemand/ALLEMAND_PROGRAMME_EDUCATIF_PREMIERE.pdf"),
    ("Allemand", "Tle", "webfetch-1791980448304-cy42hk", "dpfc_fichiers/Programmes/prg_secondaire/Allemand/ALLEMAND_PROGRAMME_EDUCATIF_TERMINAL.pdf"),
    ("Espagnol", "4e", "webfetch-1791980449108-7if4pr", "/dpfc_fichiers/Programmes/prg_secondaire/Espagnol/ESPAGNOL_4eme.pdf"),
    ("Espagnol", "3e", "webfetch-1791980449622-5gp2c8", "/dpfc_fichiers/Programmes/prg_secondaire/Espagnol/ESPAGNOL_3eme.pdf"),
    ("Espagnol", "2nde", "webfetch-1791980450826-92gy7g", "dpfc_fichiers/2019-2020/programmes%20secondaires%202e%20cycle/espagnol/ESPAGNOL%202nde.pdf"),
    ("Espagnol", "1ere", "webfetch-1791980453592-azoxgd", "dpfc_fichiers/2019-2020/programmes%20secondaires%202e%20cycle/espagnol/ESPAGNOL%201%C3%A8re.pdf"),
    ("Espagnol", "Tle", "webfetch-1791980452065-57hixt", "/dpfc_fichiers/2018-2019/programmes_guides/Espagnol/PROGR_ED_ESP_2018-2019_TLE_APC.pdf"),
    ("Francais", "6e", "webfetch-1791980465806-oqo614", "dpfc_fichiers/Programmes/prg_secondaire/Fran/PROGRAMME%20EDUCATIF%206e%20VALIDE.pdf"),
    ("Francais", "5e", "webfetch-1791980465761-9fcjyz", "dpfc_fichiers/Programmes/prg_secondaire/Fran/PROGRAMME%20EDUCATIF%205%C3%A8%20VALIDE.pdf"),
    ("Francais", "4e", "webfetch-1791980467390-9jd359", "dpfc_fichiers/Programmes/prg_secondaire/Fran/PROGRAMME%20EDUCATIF%204e%20VALIDE.pdf"),
    ("Francais", "3e", "webfetch-1791980466620-wzzfey", "dpfc_fichiers/Programmes/prg_secondaire/Fran/PROGRAMME%20EDUCATIF%203e%20VALIDE.pdf"),
    ("Francais", "2nde", "webfetch-1791980468405-glz1t6", "dpfc_fichiers/Programmes/prg_secondaire/Fran/PROGRAMME%20EDUCATIF%20SECONDE%20VALIDE.pdf"),
    ("Francais", "1ere", "webfetch-1791980468030-a0vxfk", "dpfc_fichiers/Programmes/prg_secondaire/Fran/PROGRAMME%20EDUCATIF%201re%20VALIDE.pdf"),
    ("Francais", "Tle", "webfetch-1791980469579-9rkpq4", "dpfc_fichiers/Programmes/prg_secondaire/Fran/PROGRAMME%20EDUCATIF%20TERMINALE%20VALIDE.pdf"),
]

cache, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
manifest = []
for matiere, classe, name, rel in DOCS:
    path = os.path.join(cache, name + ".pdf")
    try:
        reader = PdfReader(path)
        text = "\n".join("\n===== page %d =====\n%s" % (i, (p.extract_text() or "")) for i, p in enumerate(reader.pages, 1))
    except Exception as exc:
        print("ERREUR", matiere, classe, exc)
        continue
    url = BASE + rel.lstrip("/")
    fn = "%s_%s.txt" % (matiere, classe)
    open(os.path.join(out, fn), "w", encoding="utf-8").write(text)
    theme = len(re.findall(r"TH[EÈ]ME|THEMA|TEMA|UNIT[EÉ]?\b", text, re.I))
    lecon = len(re.findall(r"LE[CÇ]ON|LEKTION|LECCI[OÓ]N|LESSON", text, re.I))
    print("%-9s %-5s %3d pages %7d car.  themes:%3d lecons:%3d" % (matiere, classe, len(reader.pages), len(text), theme, lecon))
    manifest.append({"matiere": matiere, "classe": classe, "pages": len(reader.pages), "url": url, "fichier": fn})
json.dump(manifest, open(os.path.join(out, "_manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
