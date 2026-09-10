"""Statut d'abonnement par appareil.

Active uniquement via /api/cinetpay/webhook une fois le paiement verifie
serveur-a-serveur (jamais sur un simple retour du frontend, facile a
falsifier). Stockage : SQLite partage (voir db.py).
"""
from datetime import date

import db


def is_premium(device_id: str) -> bool:
    conn = db.get_connection()
    try:
        row = conn.execute(
            "SELECT premium FROM subscriptions WHERE device_id = ?", (device_id,)
        ).fetchone()
        return bool(row and row[0])
    finally:
        conn.close()


def set_premium(device_id: str, value: bool) -> None:
    conn = db.get_connection()
    try:
        conn.execute(
            "INSERT INTO subscriptions (device_id, premium, updated) VALUES (?, ?, ?) "
            "ON CONFLICT(device_id) DO UPDATE SET premium=excluded.premium, updated=excluded.updated",
            (device_id, int(value), date.today().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
