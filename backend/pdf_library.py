"""Bibliotheque de VRAIS sujets d'examens en PDF (contrairement a epreuves.py
qui contient des exercices originaux ecrits par l'IA).

Chaque entree pointe vers un fichier PDF stocke dans DATA_DIR/pdfs/. Les PDF
eux-memes ne sont jamais dans le code source (git) - ils sont ajoutes via
POST /api/admin/pdf-sujets (protege par ADMIN_TOKEN), a partir de sources que
l'utilisateur a legitimement obtenues (CNECE, annales papier scannees, etc.).

ATTENTION stockage : sur Render (plan gratuit), le systeme de fichiers est
EPHEMERE - un fichier ajoute ici disparait au prochain redeploiement/redemarrage
du service. Pour une vraie persistance il faudra soit un disque payant, soit un
stockage objet externe (S3, Cloudflare R2...). Pour l'instant, considerer ces
PDF comme "a re-uploader apres chaque deploiement" tant que ce n'est pas regle.
"""
import json
import os
import threading
import uuid
from datetime import date

from paths import DATA_DIR

_LOCK = threading.Lock()
_META_PATH = os.path.join(DATA_DIR, "pdf_sujets.json")
PDF_DIR = os.path.join(DATA_DIR, "pdfs")
os.makedirs(PDF_DIR, exist_ok=True)


def _load() -> list:
    if not os.path.exists(_META_PATH):
        return []
    with open(_META_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def _save(data: list) -> None:
    with open(_META_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def list_pdf_sujets(pays: str | None = None, niveau: str | None = None,
                     matiere: str | None = None) -> list:
    items = _load()
    if pays:
        items = [i for i in items if i["pays"] == pays]
    if niveau:
        items = [i for i in items if i["niveau"] == niveau]
    if matiere:
        items = [i for i in items if i["matiere"] == matiere]
    return [
        {k: v for k, v in i.items() if k != "filename"}
        for i in items
    ]


def get_pdf_sujet(sujet_id: str) -> dict | None:
    for i in _load():
        if i["id"] == sujet_id:
            return i
    return None


def add_pdf_sujet(pays: str, niveau: str, matiere: str, annee: int, titre: str,
                   source: str, file_bytes: bytes) -> dict:
    sujet_id = uuid.uuid4().hex[:16]
    filename = f"{sujet_id}.pdf"
    with open(os.path.join(PDF_DIR, filename), "wb") as f:
        f.write(file_bytes)

    entry = {
        "id": sujet_id,
        "pays": pays,
        "niveau": niveau,
        "matiere": matiere,
        "annee": annee,
        "titre": titre,
        "source": source,
        "filename": filename,
        "added": date.today().isoformat(),
    }
    with _LOCK:
        data = _load()
        data.append(entry)
        _save(data)
    return entry


def delete_pdf_sujet(sujet_id: str) -> bool:
    with _LOCK:
        data = _load()
        entry = next((i for i in data if i["id"] == sujet_id), None)
        if not entry:
            return False
        data = [i for i in data if i["id"] != sujet_id]
        _save(data)
        try:
            os.remove(os.path.join(PDF_DIR, entry["filename"]))
        except OSError:
            pass
        return True
