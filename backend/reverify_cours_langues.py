"""Seconde verification independante des lecons de langues deja generees (a lancer apres generate_cours_langues.py).
Pour chaque lecon marquee « corrige » (ou toutes avec REVERIFY_ALL=1) : nouvel appel du verificateur ;
ok -> marque « ok2 » ; corrige -> la lecon corrigee remplace l'ancienne (si valide) ; rejete -> lecon retiree du manifest.
"""
import json
import os
from concurrent.futures import ThreadPoolExecutor

import generate_cours_langues as g

ALL = os.environ.get("REVERIFY_ALL") == "1"
source = {(e["pays"], e["niveau"], e["matiere"]): e for e in json.load(open(g.SOURCE_PATH, encoding="utf-8")) if e.get("generateur") == "langues"}
manifest = json.load(open(g.MANIFEST_PATH, encoding="utf-8"))
res = {"ok2": 0, "corrige2": 0, "rejete2": 0, "erreur": 0}
removed = set()
remarks = []


def run(item):
    path = os.path.join(g.LESSONS_DIR, item["slug"] + ".json")
    rec = json.load(open(path, encoding="utf-8"))
    if rec.get("verification") not in ("ok", "corrige", "corrige2") or (rec["verification"] == "ok" and not ALL):
        return
    entry = source.get((rec["pays"], rec["niveau"], rec["matiere"]))
    if not entry:
        return
    d = entry["details"][rec["chapitre"]]
    try:
        lesson = g.LessonContent(**{k: rec[k] for k in g.LessonContent.model_fields})
        v = g.call_verify(entry, d, lesson)
        if v.statut == "ok":
            rec["verification"] = "ok2"
            res["ok2"] += 1
        elif v.statut == "corrige" and v.lecon_corrigee and not g.validate(v.lecon_corrigee, entry, rec["chapitre"]):
            fixed = v.lecon_corrigee.model_dump()
            fixed["title"] = rec["chapitre"]
            rec.update(fixed)
            rec["verification"] = "corrige2"
            res["corrige2"] += 1
            remarks.append({"slug": item["slug"], "remarques": v.remarques})
        else:
            res["rejete2"] += 1
            removed.add(item["slug"])
            remarks.append({"slug": item["slug"], "rejete": True, "remarques": v.remarques})
            return
        json.dump(rec, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception as exc:
        res["erreur"] += 1
        print("erreur", item["slug"], str(exc)[:120])


with ThreadPoolExecutor(max_workers=g.WORKERS) as pool:
    list(pool.map(run, [m for m in manifest if m.get("template") == "text_only" and m["slug"] in {x["slug"] for x in manifest}]))

if removed:
    manifest = [m for m in manifest if m["slug"] not in removed]
    json.dump(manifest, open(g.MANIFEST_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    for s in removed:
        os.remove(os.path.join(g.LESSONS_DIR, s + ".json"))
json.dump(remarks, open(os.path.join(g.SEED_DIR, "langues_reverify.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(res, "jetons", g.usage)
