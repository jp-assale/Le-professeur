"""Entonnoir d'acquisition : ouverture -> 1re question -> quota atteint ->
offre vue -> demande de paiement -> abonnement active.

Une seule ligne par appareil et par etape (la PREMIERE fois qu'il la
franchit) : de quoi compter combien d'eleves passent chaque etape, sans
journal qui grossit a chaque question. Stockage : SQLite partage (voir db.py),
sur le disque persistant en production.

Les etapes sont constatees par le serveur (ouverture = premier appel a
/api/quota, fait au demarrage par toutes les versions de l'appli ; questions,
quota, activation), sauf « offre vue » et « demande de paiement » que seule
l'appli peut signaler (route /api/funnel, a partir de la version 2.18).
"""
from datetime import datetime, timezone

import db

ETAPES = (
    ("ouverture", "1re ouverture de l'appli"),
    ("premiere_question", "1re question posée (chat, photo, quiz…)"),
    ("quota_atteint", "Questions gratuites épuisées"),
    ("offre_vue", "Offre illimitée affichée"),
    # Site : demande envoyee sur WhatsApp ; appli Android : code copie pour le bureau.
    ("demande_paiement", "Demande d'abonnement (WhatsApp ou code copié)"),
    ("paiement", "Abonnement activé"),
)
# Hors entonnoir : abonnes qui atteignent le plafond d'usage raisonnable
# (sert a verifier que ce plafond ne gene pas un usage normal).
ETAPE_PLAFOND = "plafond_premium"
# Seules etapes que l'appli peut declarer elle-meme.
ETAPES_CLIENT = {"offre_vue", "demande_paiement"}

_VALIDES = {e for e, _ in ETAPES} | {ETAPE_PLAFOND}


def record(device_id: str, etape: str, plateforme: str | None = None) -> None:
    """Note la premiere fois qu'un appareil franchit `etape` (ignore ensuite)."""
    if not device_id or etape not in _VALIDES:
        return
    conn = db.get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO funnel_events (device_id, etape, ts, plateforme) VALUES (?, ?, ?, ?)",
            (device_id, etape, datetime.now(timezone.utc).isoformat(), plateforme),
        )
        conn.commit()
    finally:
        conn.close()


def _pct(part: int, total: int) -> float | None:
    return round(100 * part / total, 1) if total else None


def summary(depuis: str | None = None) -> dict:
    """Nombre d'appareils par etape, parmi les appareils vus pour la premiere
    fois a partir de `depuis` (AAAA-MM-JJ, tous si None) - une cohorte
    d'installations, pour comparer une semaine ou une campagne a une autre."""
    conn = db.get_connection()
    try:
        cohorte = (
            "SELECT device_id FROM funnel_events GROUP BY device_id HAVING MIN(ts) >= ?"
            if depuis else "SELECT DISTINCT device_id FROM funnel_events"
        )
        params = (depuis,) if depuis else ()
        counts = dict(conn.execute(
            f"SELECT etape, COUNT(*) FROM funnel_events WHERE device_id IN ({cohorte}) GROUP BY etape",
            params,
        ).fetchall())
        plateformes = dict(conn.execute(
            "SELECT COALESCE(plateforme, 'inconnue'), COUNT(*) FROM funnel_events "
            f"WHERE etape = 'ouverture' AND device_id IN ({cohorte}) GROUP BY 1",
            params,
        ).fetchall())
    finally:
        conn.close()

    base = counts.get("ouverture", 0)
    etapes = []
    precedent = None
    for etape, label in ETAPES:
        n = counts.get(etape, 0)
        etapes.append({
            "etape": etape,
            "label": label,
            "appareils": n,
            # % des ouvertures, et % de l'etape juste avant.
            "taux_global": _pct(n, base),
            "taux_etape": _pct(n, precedent) if precedent is not None else None,
        })
        precedent = n
    return {
        "depuis": depuis,
        "etapes": etapes,
        "plafond_premium": counts.get(ETAPE_PLAFOND, 0),
        "plateformes": plateformes,
    }
