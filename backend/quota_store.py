"""Compteur de questions gratuites par appareil, avec reset quotidien.

Stockage : SQLite partage (voir db.py) - supporte correctement les acces
concurrents de plusieurs workers Gunicorn, contrairement a l'ancien fichier
JSON + verrou en memoire (qui ne protegeait qu'un seul processus a la fois).
"""
from datetime import date

import db


def _today() -> str:
    return date.today().isoformat()


def get_remaining(device_id: str, daily_limit: int) -> int:
    conn = db.get_connection()
    try:
        row = conn.execute(
            "SELECT date, count FROM quota WHERE device_id = ?", (device_id,)
        ).fetchone()
        if not row or row[0] != _today():
            return daily_limit
        return max(0, daily_limit - row[1])
    finally:
        conn.close()


def consume(device_id: str, daily_limit: int, weight: int = 1) -> int:
    """Increments today's count by `weight` and returns the remaining quota."""
    conn = db.get_connection()
    try:
        today = _today()
        # Upsert atomique : evite la fenetre lire-puis-ecrire qui pourrait
        # perdre une incrementation si deux requetes arrivent en meme temps.
        conn.execute(
            "INSERT INTO quota (device_id, date, count) VALUES (?, ?, ?) "
            "ON CONFLICT(device_id) DO UPDATE SET "
            "count = CASE WHEN quota.date = excluded.date "
            "THEN quota.count + excluded.count ELSE excluded.count END, "
            "date = excluded.date",
            (device_id, today, weight),
        )
        conn.commit()
        row = conn.execute("SELECT count FROM quota WHERE device_id = ?", (device_id,)).fetchone()
        return max(0, daily_limit - row[0])
    finally:
        conn.close()
