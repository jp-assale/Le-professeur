"""Compteur de questions gratuites par appareil, avec reset quotidien.

Stockage MVP: fichier JSON local. A remplacer par une vraie base (ex. Supabase,
Postgres) avant une mise en production a plusieurs instances.
"""
import json
import os
import threading
from datetime import date

from paths import DATA_DIR

_LOCK = threading.Lock()
_STORE_PATH = os.path.join(DATA_DIR, "quota.json")


def _today() -> str:
    return date.today().isoformat()


def _load() -> dict:
    if not os.path.exists(_STORE_PATH):
        return {}
    with open(_STORE_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save(data: dict) -> None:
    with open(_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)


def get_remaining(device_id: str, daily_limit: int) -> int:
    with _LOCK:
        data = _load()
        entry = data.get(device_id)
        if not entry or entry.get("date") != _today():
            return daily_limit
        return max(0, daily_limit - entry.get("count", 0))


def consume(device_id: str, daily_limit: int, weight: int = 1) -> int:
    """Increments today's count by `weight` and returns the remaining quota."""
    with _LOCK:
        data = _load()
        entry = data.get(device_id)
        if not entry or entry.get("date") != _today():
            entry = {"date": _today(), "count": 0}
        entry["count"] += weight
        data[device_id] = entry
        _save(data)
        return max(0, daily_limit - entry["count"])
