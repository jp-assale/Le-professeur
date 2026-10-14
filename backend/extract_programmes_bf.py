"""Texte des guides officiels du Burkina Faso (education.gov.bf, MENAPLN) lus avec l'outil de lecture web.
Meme principe que extract_programmes_ci.py : lit les copies locales deja en cache, ne telecharge rien.

Usage : python extract_programmes_bf.py <dossier_cache_pdf> <dossier_sortie>
"""
import json
import os
import sys

from pypdf import PdfReader

BASE = "https://www.education.gov.bf/fileadmin/user_upload/storages/espace_enseignant/guides/post_primaire/"
DOCS = [
    # (matiere, classe, fichier cache, nom du PDF sur le site)
    ("Anglais", "6e", "webfetch-1791981792880-zh75vg", "guide_anglais_6-5e.pdf"),
    ("Anglais", "5e", "webfetch-1791981792880-zh75vg", "guide_anglais_6-5e.pdf"),
    ("Allemand", "4e", "webfetch-1791994090188-371cvk", "guide_allemand_4e.pdf"),
    ("Francais", "4e", "webfetch-1791994080144-lknhwj", "guide_francais_4e_3e.pdf"),
    ("Francais", "3e", "webfetch-1791994080144-lknhwj", "guide_francais_4e_3e.pdf"),
]
cache, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
manifest = []
for matiere, classe, name, pdf in DOCS:
    reader = PdfReader(os.path.join(cache, name + ".pdf"))
    text = "\n".join("\n===== page %d =====\n%s" % (i, (p.extract_text() or "")) for i, p in enumerate(reader.pages, 1))
    fn = "BF_%s_%s.txt" % (matiere, classe)
    open(os.path.join(out, fn), "w", encoding="utf-8").write(text)
    print("%-9s %-4s %3d pages %7d car." % (matiere, classe, len(reader.pages), len(text)))
    manifest.append({"matiere": matiere, "classe": classe, "pages": len(reader.pages), "url": BASE + pdf,
                     "fichier": fn, "pays": "burkina_faso", "pays_label": "Burkina Faso"})
json.dump(manifest, open(os.path.join(out, "_manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
