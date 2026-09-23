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


def set_premium(device_id: str, value: bool, days: int = DEFAULT_DURATION_DAYS,
                 contact: str | None = None) -> str | None:
    """Active (avec expiration dans `days` jours) ou desactive l'abonnement.
    `contact` (numero WhatsApp) n'est mis a jour que si fourni - une
    desactivation ou une reactivation sans le repreciser garde l'ancien.
    Retourne la date d'expiration (ISO) si active, None si desactive."""
    until = (date.today() + timedelta(days=days)).isoformat() if value else None
    conn = db.get_connection()
    try:
        if contact:
            conn.execute(
                "INSERT INTO subscriptions (device_id, premium, updated, premium_until, contact) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(device_id) DO UPDATE SET premium=excluded.premium, updated=excluded.updated, "
                "premium_until=excluded.premium_until, contact=excluded.contact",
                (device_id, int(value), date.today().isoformat(), until, contact),
            )
        else:
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


def list_subscriptions() -> list[dict]:
    """Toutes les activations connues (actives, expirees ou desactivees),
    triees par date d'expiration - pour le tableau de suivi admin."""
    conn = db.get_connection()
    try:
        rows = conn.execute(
            "SELECT device_id, premium, premium_until, contact, updated FROM subscriptions "
            "ORDER BY premium_until IS NULL, premium_until ASC"
        ).fetchall()
    finally:
        conn.close()

    today = date.today().isoformat()
    result = []
    for device_id, premium, premium_until, contact, updated in rows:
        active = bool(premium) and (not premium_until or premium_until >= today)
        days_left = None
        if premium_until:
            days_left = (date.fromisoformat(premium_until) - date.today()).days
        result.append({
            "device_id": device_id,
            "active": active,
            "premium_until": premium_until,
            "contact": contact,
            "days_left": days_left,
            "updated": updated,
        })
    return result
