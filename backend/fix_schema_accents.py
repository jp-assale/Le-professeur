"""Ajoute les accents manquants dans les schemas de cours deja VERIFIES
(generate_cours_schemas.py), sans rien changer d'autre.

Garde-fou : le texte renvoye par le modele n'est accepte que si, une fois les
accents retires et les majuscules ignorees, il est IDENTIQUE a l'original
(titre, racine, centre, et chaque label/detail). Le contenu verifie
scientifiquement ne peut donc pas etre modifie par cette passe - seulement
orthographie correctement. Si le controle echoue, le schema reste tel quel.

Usage : python fix_schema_accents.py
"""
import glob
import json
import os
import re
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

LESSONS_DIR = os.path.join(os.path.dirname(__file__), "cours_seed", "lessons")
MODEL = os.environ.get("SCHEMA_FIX_MODEL", "claude-sonnet-5")
client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
_lock = threading.Lock()


def strip(s: str) -> str:
    s = s.replace("œ", "oe").replace("Œ", "oe").replace("æ", "ae").replace("’", "'")
    n = unicodedata.normalize("NFD", s)
    return re.sub(r"\s+", " ", "".join(c for c in n if not unicodedata.combining(c))).strip().lower()


def texts(schema: dict) -> list:
    out = [schema.get("titre", ""), schema.get("racine", ""), schema.get("centre", "")]
    for it in schema["items"]:
        out += [it.get("label", ""), it.get("detail", "")]
    return out


def same_text_modulo_accents(old: dict, new: dict) -> bool:
    if old.get("type") != new.get("type") or len(old["items"]) != len(new.get("items", [])):
        return False
    return all(strip(a) == strip(b) for a, b in zip(texts(old), texts(new)))


def fix(schema: dict) -> dict | None:
    prompt = (
        "Voici un schema scolaire en JSON. Reecris EXACTEMENT le meme JSON en "
        "ajoutant uniquement les accents, cedilles, apostrophes typographiques "
        "et ligatures francais manquants (é, è, ê, à, ù, ç, œ...). Ne change "
        "aucun mot, aucun chiffre, aucune unite, aucune structure, aucune cle. "
        "Reponds UNIQUEMENT avec le JSON, sans texte autour.\n\n"
        + json.dumps(schema, ensure_ascii=False)
    )
    r = client.messages.create(model=MODEL, max_tokens=4000, messages=[{"role": "user", "content": prompt}])
    raw = "".join(b.text for b in r.content if b.type == "text")
    new, _ = json.JSONDecoder().raw_decode(raw[raw.find("{"):])
    return new if same_text_modulo_accents(schema, new) else None


def handle(path: str, lesson: dict, stats: dict):
    try:
        new = fix(lesson["schema"])
    except Exception as exc:
        with _lock:
            stats["erreurs"] += 1
            print(f"  [ERREUR] {lesson['slug']} : {exc}", flush=True)
        return
    with _lock:
        if new is None:
            stats["controle_refuse"] += 1
            print(f"  [REFUSE] {lesson['slug']} (texte different, conserve tel quel)", flush=True)
            return
        changed = json.dumps(new, ensure_ascii=False) != json.dumps(lesson["schema"], ensure_ascii=False)
        lesson["schema"] = new
        with open(path, "w", encoding="utf-8") as f:
            json.dump(lesson, f, ensure_ascii=False, indent=2)
        stats["modifies" if changed else "inchanges"] += 1
        print(f"  [{'ACCENTS AJOUTES' if changed else 'deja bon'}] {lesson['slug']}", flush=True)


def main():
    todo = []
    for path in sorted(glob.glob(os.path.join(LESSONS_DIR, "*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            lesson = json.load(f)
        if lesson.get("schema_status") in ("ok", "corrige") and lesson.get("schema"):
            todo.append((path, lesson))
    print(f"{len(todo)} schema(s) a traiter.", flush=True)
    stats = {"modifies": 0, "inchanges": 0, "controle_refuse": 0, "erreurs": 0}
    with ThreadPoolExecutor(max_workers=6) as pool:
        for path, lesson in todo:
            pool.submit(handle, path, lesson, stats)
    print(f"\nTermine. {stats}")


if __name__ == "__main__":
    main()
