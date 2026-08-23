"""Signalements envoyes par les eleves quand un exercice ou une reponse semble
faux (faiblesse #2 : contenu non relu par un enseignant). Sert de relecture
qualite crowdsourcee en attendant une vraie validation humaine du contenu.
"""
import json
import os
import threading
from datetime import datetime, timezone

from paths import DATA_DIR

_LOCK = threading.Lock()
_LOG_PATH = os.path.join(DATA_DIR, "reports.jsonl")


def add_report(device_id: str, context: str, excerpt: str, comment: str) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "device_id": device_id,
        "context": context[:200],
        "excerpt": excerpt[:800],
        "comment": comment[:500],
    }
    with _LOCK:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
