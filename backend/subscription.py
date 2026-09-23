"""Statut d'abonnement par appareil.

Active via /api/cinetpay/webhook une fois le paiement verifie serveur-a-
serveur (jamais sur un simple retour du frontend, facile a falsifier), ou
manuellement depuis la page admin (paiement Mobile Money direct en attendant
l'activation de CinetPay/PayDunya). Stockage : SQLite partage (voir db.py).

L'abonnement expire automatiquement apres DEFAULT_DURATION_DAYS jours (voir
premium_until) - un paiement ne rend pas premium a vie, il faut reactiver a
chaque renouvellement.
"""
from datetime import date, timedelta

import db

DEFAULT_DURATION_DAYS = 30


def is_premium(device_id: str) -> bool:
    conn = db.get_connection()
    try:
        row = conn.execute(
            "SELECT premium, premium_until FROM subscriptions WHERE device_id = ?", (device_id,)
        ).fetchone()
        if not row or not row[0]:
            return False
        premium_until = row[1]
        # Pas de date d'expiration enregistree (anciennes activations avant
        # l'ajout de cette colonne) : on la considere valide plutot que de
        # couper l'acces sans preavis a quelqu'un de deja abonne.
        if not premium_until:
            return True
        return premium_until >= date.today().isoformat()
    finally:
        conn.close()


def get_premium_until(device_id: str) -> str | None:
    conn = db.get_connection()
    try:
        row = conn.execute(
            "SELECT premium_until FROM subscriptions WHERE device_id = ? AND premium = 1", (device_id,)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def set_premium(device_id: str, value: bool, days: int = DEFAULT_DURATION_DAYS) -> str | None:
    """Active (avec expiration dans `days` jours) ou desactive l'abonnement.
    Retourne la date d'expiration (ISO) si active, None si desactive."""
    until = (date.today() + timedelta(days=days)).isoformat() if value else None
    conn = db.get_connection()
    try:
        conn.execute(
            "INSERT INTO subscriptions (device_id, premium, updated, premium_until) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(device_id) DO UPDATE SET premium=excluded.premium, updated=excluded.updated, "
            "premium_until=excluded.premium_until",
            (device_id, int(value), date.today().isoformat(), until),
        )
        conn.commit()
    finally:
        conn.close()
    return until
