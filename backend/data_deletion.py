"""Suppression des donnees d'un appareil (droit a l'effacement, exige par Google
Play pour la declaration « Securite des donnees »).

Efface tout ce qui est rattache a un code appareil : progression, profils
pedagogiques, signalements, transactions et compteur de questions. Un
abonnement encore actif n'est supprime que si l'admin le demande
(`include_subscription`), car sa suppression fait perdre l'acces illimite paye.
"""
from datetime import date

import db


def delete_device_data(device_id: str, include_subscription: bool = False) -> dict:
    """Retourne le nombre de lignes supprimees par table."""
    device_id = (device_id or "").strip()
    if not device_id:
        raise ValueError("device_id manquant")
    conn = db.get_connection()
    counts = {}
    try:
        for table in ("progress_events", "profiles", "reports", "payments", "quota"):
            counts[table] = conn.execute(
                "DELETE FROM %s WHERE device_id = ?" % table, (device_id,)
            ).rowcount

        row = conn.execute(
            "SELECT premium, premium_until FROM subscriptions WHERE device_id = ?", (device_id,)
        ).fetchone()
        active = bool(row and row[0] and (not row[1] or row[1] >= date.today().isoformat()))
        if row and (include_subscription or not active):
            # Abonnement expire ou desactive : plus aucune raison de garder le contact.
            counts["subscriptions"] = conn.execute(
                "DELETE FROM subscriptions WHERE device_id = ?", (device_id,)
            ).rowcount
        else:
            counts["subscriptions"] = 0
        counts["abonnement_actif_conserve"] = int(bool(row) and counts["subscriptions"] == 0)
        conn.commit()
    finally:
        conn.close()
    return counts
