"""Audit statique + donnees (hors reseau IA). Usage : python _audit_system.py"""
import collections
import glob
import json
import os
import py_compile
import random
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import requests

sys.path.insert(0, os.path.dirname(__file__))
from curriculum import MATIERES, NIVEAUX, PAYS  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
problems = []


def section(t):
    print("\n=== " + t + " ===")


def bad(msg):
    problems.append(msg)
    print("  [PROBLEME] " + msg)


# ---------------------------------------------------------------- A. statique
section("A. Code et fichiers")
for p in sorted(glob.glob(os.path.join(ROOT, "backend", "*.py"))):
    if os.path.basename(p).startswith("audit_"):
        continue
    try:
        py_compile.compile(p, doraise=True)
    except Exception as e:
        bad("Python invalide : %s : %s" % (os.path.basename(p), e))
print("  Python : %d fichiers compiles" % len(glob.glob(os.path.join(ROOT, "backend", "*.py"))))

js = sorted(glob.glob(os.path.join(ROOT, "frontend", "js", "*.js")))
for p in js:
    r = subprocess.run(["node", "--check", p], capture_output=True, text=True)
    if r.returncode:
        bad("JS invalide : %s : %s" % (os.path.basename(p), r.stderr.strip()[:200]))
print("  JS : %d fichiers verifies" % len(js))

for p in glob.glob(os.path.join(ROOT, "frontend", "*.html")):
    base = os.path.basename(p)
    if base.startswith(("cours-pilote", "pilote-")):
        continue
    html = open(p, encoding="utf-8").read()
    for ref in re.findall(r'(?:src|href)="([^"#?]+)"', html):
        if ref.startswith(("http", "data:", "mailto:", "tel:", "/api")) or ref.endswith(".html") and ref.startswith("/"):
            continue
        if not os.path.exists(os.path.join(ROOT, "frontend", ref)):
            bad("%s reference un fichier absent : %s" % (base, ref))
sw = open(os.path.join(ROOT, "frontend", "service-worker.js"), encoding="utf-8").read()
for f in re.findall(r'"(/[^"]+\.[a-z0-9]+)"', sw):
    if not os.path.exists(os.path.join(ROOT, "frontend", f.lstrip("/"))):
        bad("service-worker : fichier absent : " + f)
print("  HTML / service worker : references verifiees")

# ---------------------------------------------------------------- B. cours
section("B. Cours (lecons)")
manifest = json.load(open(os.path.join(ROOT, "backend", "cours_seed", "manifest.json"), encoding="utf-8"))
files = {os.path.basename(p)[:-5]: p for p in glob.glob(os.path.join(ROOT, "backend", "cours_seed", "lessons", "*.json"))}
slugs = {m["slug"] for m in manifest}
print("  manifest : %d lecons ; fichiers : %d" % (len(slugs), len(files)))
for s in sorted(slugs - set(files)):
    bad("manifest sans fichier : " + s)
for s in sorted(set(files) - slugs):
    bad("fichier absent du manifest : " + s)

matrix = collections.Counter()
status = collections.Counter()
mojibake = re.compile("�|Ã[ -¿]|â€")
unacc = re.compile(r"\b(electri\w*|energie|reseau\w*|systeme\w*|quantite|matiere|reaction\w*|metabol\w*|hypothese|theoreme|probleme|resultat)\b", re.I)
issues = collections.defaultdict(list)


def all_text(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, list):
        for x in v:
            yield from all_text(x)
    elif isinstance(v, dict):
        for k, x in v.items():
            if k in ("schema", "slug", "source", "template", "schema_status", "pays", "niveau", "examen", "matiere", "serie"):
                continue
            yield from all_text(x)


for slug, p in files.items():
    d = json.load(open(p, encoding="utf-8"))
    matrix[(d.get("pays"), d.get("niveau"), d.get("matiere"))] += 1
    status[d.get("schema_status") or "-"] += 1
    for key, sub in (("intro", "body"), ("concept", "explanation"), ("concept", "highlight"), ("example", "problem")):
        if not (d.get(key) or {}).get(sub, "").strip():
            issues["champ vide %s.%s" % (key, sub)].append(slug)
    if not (d.get("example") or {}).get("steps"):
        issues["exemple sans etapes"].append(slug)
    q = d.get("quiz") or {}
    ch = q.get("choices") or []
    if len(ch) < 3:
        issues["quiz : moins de 3 choix"].append(slug)
    if sum(1 for c in ch if c.get("correct")) != 1:
        issues["quiz : pas exactement 1 bonne reponse"].append(slug)
    labels = [c.get("label", "").strip() for c in ch]
    if len(set(labels)) != len(labels):
        issues["quiz : choix en double"].append(slug)
    if not q.get("question", "").strip() or not q.get("feedback_correct") or not q.get("feedback_wrong"):
        issues["quiz : question/feedback manquant"].append(slug)
    pts = ((d.get("resume") or {}).get("points")) or []
    if len(pts) < 2:
        issues["resume : moins de 2 points"].append(slug)
    txt = " ".join(all_text(d))
    if mojibake.search(txt):
        issues["caracteres corrompus"].append(slug)
    if unacc.search(txt):
        issues["mot francais sans accent"].append(slug)
    if txt.count("$") % 2:
        issues["nombre impair de $ (formule non fermee)"].append(slug)
    if d.get("schema_status") in ("ok", "corrige") and not d.get("schema"):
        issues["schema_status ok sans schema"].append(slug)
    if d.get("schema_status") == "rejete" and d.get("schema"):
        issues["schema rejete mais present (sera-t-il affiche ?)"].append(slug)
for k, v in sorted(issues.items(), key=lambda kv: -len(kv[1])):
    bad("%s : %d lecon(s), ex. %s" % (k, len(v), ", ".join(x[:45] for x in v[:2])))
print("  statuts de schema :", dict(status))

section("C. Couverture pays x niveau x matiere (lecons / sujets PDF)")
pdfs = json.load(open(os.path.join(ROOT, "backend", "pdf_seed", "manifest.json"), encoding="utf-8"))
pdf_matrix = collections.Counter((x["pays"], x["niveau"], x["matiere"]) for x in pdfs)
ids = [x["id"] for x in pdfs]
if len(ids) != len(set(ids)):
    bad("identifiants PDF en double")
unknown = [k for k in pdf_matrix if k[0] not in {p["code"] for p in PAYS} or k[2] not in MATIERES]
print("  %d sujets PDF ; %d lecons ; combinaisons inconnues du referentiel : %d" % (len(pdfs), len(files), len(unknown)))
for k in unknown[:5]:
    bad("sujet PDF hors referentiel : %s" % (k,))
for niv in [n["code"] for n in NIVEAUX]:
    print("  -- niveau %s" % niv)
    head = "     %-14s" % "matiere" + "".join("%-12s" % p["code"][:11] for p in PAYS)
    print(head + "   (lecons/pdf)")
    for mat in MATIERES:
        row = "     %-14s" % mat[:13]
        for p in PAYS:
            c, f = matrix.get((p["code"], niv, mat), 0), pdf_matrix.get((p["code"], niv, mat), 0)
            row += "%-12s" % ("%d/%d" % (c, f) if c or f else "-")
        print(row)

section("D. Disponibilite des PDF (echantillon de 80, HEAD)")
random.seed(7)
sample = random.sample(pdfs, min(80, len(pdfs)))


def head(x):
    try:
        r = requests.head(x["url"], allow_redirects=True, timeout=25)
        return x, r.status_code, int(r.headers.get("content-length", 0) or 0)
    except Exception as e:
        return x, 0, str(e)[:60]


with ThreadPoolExecutor(8) as pool:
    results = list(pool.map(head, sample))
ko = [(x["id"], s, n) for x, s, n in results if s != 200]
print("  accessibles : %d / %d" % (len(results) - len(ko), len(results)))
for k in ko[:8]:
    bad("PDF injoignable : %s -> %s %s" % k)

print("\nRESUME : %d probleme(s) releves." % len(problems))
