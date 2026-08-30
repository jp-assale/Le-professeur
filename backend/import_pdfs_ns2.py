"""Script ponctuel : importe le lot "ns2" fourni par l'utilisateur -
C:\\Users\\jp.assale\\Desktop\\Claude\\ns2. Deux types de contenu :
  - Nouveaux sujets Philosophie (+ "Devoirs et Blancs") : matiere fixee
  - sujet examens BAC/DEF <pays> : meme structure que le tout premier
    import (import_pdfs.py) - CE LOT RECOUVRE LARGEMENT LA BIBLIOTHEQUE
    EXISTANTE (analyse prealable : 546/865 fichiers sont des doublons
    exacts pays+niveau+matiere+titre). Ce script les detecte et les
    ignore automatiquement plutot que de les reimporter en double.
"""
import json
import os
import re
import time
import uuid

import requests

SOURCE_DIR = r"C:\Users\jp.assale\Desktop\Claude\ns2"
TOKEN_PATH = os.path.join(os.path.dirname(__file__), ".github_token")
MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "pdf_seed", "manifest.json")
REPO = "jp-assale/Le-professeur"
# pdf-sujets-v1 est plein (1000/1000), v2 a de la place (303/1000 avant ce lot).
RELEASE_TAGS = ["pdf-sujets-v2", "pdf-sujets-v3"]

FOLDER_MAP = {
    "sujet examens bac benin": ("benin", "lycee", None),
    "sujet examens bac cote d'ivoire": ("cote_ivoire", "lycee", None),
    "sujet examens bac guinee": ("guinee", "lycee", None),
    "sujet examens bac senegal": ("senegal", "lycee", None),
    "sujet examens def mali": ("mali", "college", None),
    "nouveaux sujets philosophie/mali": ("mali", "lycee", "Philosophie"),
    "nouveaux sujets philosophie/burkina faso": ("burkina_faso", "lycee", "Philosophie"),
    "nouveaux sujets philosophie/senegal": ("senegal", "lycee", "Philosophie"),
    "nouveaux sujets philosophie - devoirs et blancs/burkina faso": ("burkina_faso", "lycee", "Philosophie"),
    "nouveaux sujets philosophie - devoirs et blancs/cote ivoire": ("cote_ivoire", "lycee", "Philosophie"),
    "nouveaux sujets philosophie - devoirs et blancs/cote ivoire - exercices thematiques": ("cote_ivoire", "lycee", "Philosophie"),
    "nouveaux sujets philosophie - devoirs et blancs/guinee": ("guinee", "lycee", "Philosophie"),
    "nouveaux sujets philosophie - devoirs et blancs/mali": ("mali", "lycee", "Philosophie"),
}

MATIERE_PATTERNS = [
    (re.compile(r"histoire|g[ée]o", re.I), "Histoire-Geographie"),
    (re.compile(r"physique|chimie|\bpct\b|\bpc\b", re.I), "Physique-Chimie"),
    (re.compile(r"\bsvt\b|sciences.*naturelles|biologie", re.I), "SVT"),
    (re.compile(r"maths?|math[ée]matiques", re.I), "Mathematiques"),
    (re.compile(r"fran[cç]ais|r[ée]daction|dict[ée]e|linguistique", re.I), "Francais"),
    (re.compile(r"anglais", re.I), "Anglais"),
    (re.compile(r"philosophie", re.I), "Philosophie"),
]


def guess_matiere(name: str):
    for pattern, matiere in MATIERE_PATTERNS:
        if pattern.search(name):
            return matiere
    return None


def guess_annee(name: str):
    m = re.search(r"(19|20)\d{2}", name)
    return int(m.group(0)) if m else 0


def norm_title(t: str) -> str:
    t = t.lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(t.split())


def load_token() -> str:
    with open(TOKEN_PATH, "r", encoding="utf-8") as f:
        return f.read().strip()


def load_manifest() -> list:
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_manifest(data: list) -> None:
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def get_or_create_release(session: requests.Session, tag: str) -> dict:
    resp = session.get(f"https://api.github.com/repos/{REPO}/releases/tags/{tag}")
    if resp.status_code == 200:
        return resp.json()
    resp = session.post(
        f"https://api.github.com/repos/{REPO}/releases",
        json={
            "tag_name": tag,
            "name": "Bibliotheque de sujets d'examen (PDF)",
            "body": "Stockage des PDF de sujets d'examens - utilise par l'appli, pas une vraie version logicielle.",
            "draft": False,
            "prerelease": False,
        },
    )
    resp.raise_for_status()
    return resp.json()


class ReleaseFull(Exception):
    pass


def upload_asset(session: requests.Session, tag: str, upload_url: str, sujet_id: str, file_bytes: bytes) -> str:
    upload_url = upload_url.split("{")[0]
    resp = session.post(
        upload_url,
        params={"name": f"{sujet_id}.pdf"},
        data=file_bytes,
        headers={"Content-Type": "application/pdf"},
        timeout=60,
    )
    if resp.status_code == 422:
        body = resp.json()
        for err in body.get("errors", []):
            if err.get("field") == "file_count":
                raise ReleaseFull(tag)
        assets_resp = session.get(f"https://api.github.com/repos/{REPO}/releases/tags/{tag}")
        assets_resp.raise_for_status()
        for asset in assets_resp.json().get("assets", []):
            if asset["name"] == f"{sujet_id}.pdf":
                return asset["browser_download_url"]
        raise RuntimeError(f"Asset {sujet_id}.pdf: 422 non reconnu: {resp.text[:300]}")
    resp.raise_for_status()
    return resp.json()["browser_download_url"]


def main():
    token = load_token()
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    })

    release_index = 0
    release = get_or_create_release(session, RELEASE_TAGS[release_index])
    current_tag = RELEASE_TAGS[release_index]
    upload_url = release["upload_url"]
    print(f"Release prete : {release['html_url']}")

    manifest = load_manifest()
    known_sources = {e.get("_source") for e in manifest if e.get("_source")}
    existing_keys = {
        (e["pays"], e["niveau"], e["matiere"], norm_title(e["titre"]))
        for e in manifest
    }

    all_files = []
    for root, _dirs, files in os.walk(SOURCE_DIR):
        rel = os.path.relpath(root, SOURCE_DIR).replace("\\", "/").lower()
        for fname in files:
            if fname.lower().endswith(".pdf"):
                all_files.append((root, rel, fname))

    print(f"{len(all_files)} fichiers PDF trouves.")

    imported = 0
    skipped_known_folder_missing = 0
    skipped_no_matiere = []
    skipped_duplicates = []
    errors = []

    for i, (root, rel, fname) in enumerate(all_files, 1):
        source_rel = os.path.join(os.path.basename(os.path.dirname(root)), os.path.basename(root), fname)
        if source_rel in known_sources:
            continue

        mapping = FOLDER_MAP.get(rel)
        if not mapping:
            skipped_known_folder_missing += 1
            print(f"[dossier inconnu] {rel!r} ({fname})")
            continue
        pays, niveau, matiere_fixe = mapping

        matiere = matiere_fixe or guess_matiere(fname)
        if not matiere:
            skipped_no_matiere.append(source_rel)
            continue

        titre = fname[:-4] if fname.lower().endswith(".pdf") else fname
        key = (pays, niveau, matiere, norm_title(titre))
        if key in existing_keys:
            skipped_duplicates.append(source_rel)
            continue

        annee = guess_annee(fname)
        sujet_id = uuid.uuid4().hex[:16]
        full_path = os.path.join(root, fname)
        try:
            with open(full_path, "rb") as f:
                file_bytes = f.read()
        except Exception as exc:
            errors.append((source_rel, str(exc)))
            print(f"[ERREUR lecture] {source_rel}: {exc}")
            continue

        download_url = None
        for _attempt in range(len(RELEASE_TAGS)):
            try:
                download_url = upload_asset(session, current_tag, upload_url, sujet_id, file_bytes)
                break
            except ReleaseFull:
                release_index += 1
                if release_index >= len(RELEASE_TAGS):
                    errors.append((source_rel, "plus aucune release disponible (ajouter un tag a RELEASE_TAGS)"))
                    break
                current_tag = RELEASE_TAGS[release_index]
                release = get_or_create_release(session, current_tag)
                upload_url = release["upload_url"]
                print(f"--- Release pleine, bascule vers {current_tag} : {release['html_url']} ---")
            except Exception as exc:
                errors.append((source_rel, str(exc)))
                print(f"[ERREUR] {source_rel}: {exc}")
                break

        if download_url is None:
            continue

        entry = {
            "id": sujet_id,
            "pays": pays,
            "niveau": niveau,
            "matiere": matiere,
            "annee": annee,
            "titre": titre,
            "source": "Fourni par l'utilisateur",
            "url": download_url,
            "added": time.strftime("%Y-%m-%d"),
            "_source": source_rel,
        }
        manifest.append(entry)
        existing_keys.add(key)
        imported += 1

        if imported % 25 == 0:
            save_manifest(manifest)
            print(f"[{i}/{len(all_files)}] {imported} importes, sauvegarde intermediaire.")

    save_manifest(manifest)

    print("\n=== RESUME ===")
    print(f"Importes avec succes : {imported}")
    print(f"Dossiers non reconnus : {skipped_known_folder_missing}")
    print(f"Doublons ignores : {len(skipped_duplicates)}")
    print(f"Matiere non identifiee : {len(skipped_no_matiere)}")
    for s in skipped_no_matiere[:30]:
        print("   -", s)
    print(f"Erreurs : {len(errors)}")
    for s, e in errors[:30]:
        print("   -", s, ":", e)


if __name__ == "__main__":
    main()
