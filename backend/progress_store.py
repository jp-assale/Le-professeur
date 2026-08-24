"""Journal de progression par eleve (device_id) : sert au tableau de bord
(suivi de progression) et aux notes de profil (issues du diagnostic initial)
qui personnalisent les futures explications.
"""
import json
import os
import threading
from datetime import datetime, timezone

from paths import DATA_DIR

_LOCK = threading.Lock()
_LOG_PATH = os.path.join(DATA_DIR, "progress.jsonl")
_PROFILE_PATH = os.path.join(DATA_DIR, "profiles.json")


def log_event(device_id: str, event_type: str, pays: str, niveau: str, matiere: str,
              score: int | None = None, total: int | None = None) -> None:
    """event_type: 'ask' | 'quiz' | 'diagnostic' | 'correction'"""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "device_id": device_id,
        "type": event_type,
        "pays": pays,
        "niveau": niveau,
        "matiere": matiere,
        "score": score,
        "total": total,
    }
    try:
        with _LOCK:
            with open(_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass  # le suivi ne doit jamais faire echouer une reponse a l'eleve


def get_progress(device_id: str) -> dict:
    """Agrege l'activite d'un eleve par matiere : nb de questions, score moyen
    aux quiz/diagnostics/corrections, derniere activite."""
    by_matiere: dict[str, dict] = {}
    if not os.path.exists(_LOG_PATH):
        return {"matieres": []}

    with open(_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("device_id") != device_id:
                continue

            m = entry.get("matiere", "?")
            bucket = by_matiere.setdefault(m, {
                "matiere": m, "questions": 0, "quiz_scores": [], "last_activity": None,
            })
            if entry["type"] == "ask":
                bucket["questions"] += 1
            elif entry["type"] in ("quiz", "diagnostic", "correction") and entry.get("total"):
                bucket["quiz_scores"].append(entry["score"] / entry["total"])
            if not bucket["last_activity"] or entry["ts"] > bucket["last_activity"]:
                bucket["last_activity"] = entry["ts"]

    result = []
    for m, bucket in by_matiere.items():
        scores = bucket["quiz_scores"]
        avg = round(100 * sum(scores) / len(scores)) if scores else None
        result.append({
            "matiere": m,
            "questions": bucket["questions"],
            "quiz_count": len(scores),
            "avg_score_pct": avg,
            "last_activity": bucket["last_activity"],
        })
    result.sort(key=lambda r: r["last_activity"] or "", reverse=True)
    return {"matieres": result}


def _load_profiles() -> dict:
    if not os.path.exists(_PROFILE_PATH):
        return {}
    with open(_PROFILE_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save_profiles(data: dict) -> None:
    with open(_PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def set_profile_note(device_id: str, matiere: str, note: str) -> None:
    with _LOCK:
        data = _load_profiles()
        data.setdefault(device_id, {})[matiere] = note
        _save_profiles(data)


def get_profile_note(device_id: str, matiere: str) -> str | None:
    return _load_profiles().get(device_id, {}).get(matiere)
