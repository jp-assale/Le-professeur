"""Signalements envoyes par les eleves quand un exercice ou une reponse semble
faux. Sert de relecture qualite crowdsourcee en attendant une vraie
validation humaine du contenu. Stockage : SQLite partage (voir db.py)."""
from datetime import datetime, timezone

import db


def add_report(device_id: str, context: str, excerpt: str, comment: str) -> None:
    conn = db.get_connection()
    try:
        conn.execute(
            "INSERT INTO reports (ts, device_id, context, excerpt, comment) VALUES (?, ?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), device_id, context[:200], excerpt[:800], comment[:500]),
        )
        conn.commit()
    finally:
        conn.close()
