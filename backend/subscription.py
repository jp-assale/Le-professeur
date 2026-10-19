"""Statut d'abonnement par appareil.

Active via /api/cinetpay/webhook une fois le paiement verifie serveur-a-
serveur (jamais sur un simple retour du frontend, facile a falsifier), ou
manuellement depuis la page admin (paiement Mobile Money direct en attendant
l'activation de CinetPay/PayDunya). Stockage : SQLite partage (voir db.py).

L'abonnement expire automatiquement apres DEFAULT_DURATION_DAYS jours (voir
premium_until) - un paiement ne rend pas premium a vie, il faut reactiver a
chaque renouvellement.
"""
import re
import secrets
import threading
from datetime import date, datetime, timedelta, timezone

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


def activate_request(request_id: str, device_id: str, days: int, nom: str | None = None,
                     contact: str | None = None) -> dict:
    """Valide UNE demande d'abonnement envoyee par l'eleve (lien de validation
    WhatsApp) : une seule activation par `request_id`, meme si l'admin touche
    deux fois le lien. Si l'eleve est deja abonne, la duree s'ajoute a ce qui
    lui reste (renouvellement anticipe sans perte de jours).

    Retourne {"already": bool, "premium_until": "AAAA-MM-JJ", "device_id", "days"}."""
    now = datetime.now(timezone.utc).isoformat()
    conn = db.get_connection()
    try:
        inserted = conn.execute(
            "INSERT OR IGNORE INTO activation_requests (request_id, device_id, days, nom, contact, ts) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (request_id, device_id, days, nom, contact, now),
        ).rowcount
        conn.commit()
        if not inserted:
            row = conn.execute(
                "SELECT device_id, days, premium_until FROM activation_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            return {"already": True, "device_id": row[0], "days": row[1], "premium_until": row[2]}
    finally:
        conn.close()

    # Duree a ajouter a ce qu'il reste d'un abonnement encore actif.
    remaining = 0
    if is_premium(device_id):
        current = get_premium_until(device_id)
        if current:
            remaining = max(0, (date.fromisoformat(current) - date.today()).days)
    until = set_premium(device_id, True, days=days + remaining, contact=contact or nom)

    conn = db.get_connection()
    try:
        conn.execute("UPDATE activation_requests SET premium_until = ? WHERE request_id = ?", (until, request_id))
        conn.commit()
    finally:
        conn.close()
    return {"already": False, "device_id": device_id, "days": days, "premium_until": until}


def extend_premium(device_id: str, days: int) -> str:
    """Active ou prolonge l'abonnement de `days` jours, en ajoutant ce qu'il reste d'un abonnement
    encore actif (paiement automatique : meme regle que activate_request). Retourne la date de fin."""
    remaining = 0
    if is_premium(device_id):
        current = get_premium_until(device_id)
        if current:
            remaining = max(0, (date.fromisoformat(current) - date.today()).days)
    return set_premium(device_id, True, days=days + remaining)


# --- Code d'abonnement (XXXX-XXXX) ---
# L'eleve s'abonne sur le site ; le site lui donne ce code court, qu'il tape dans l'appli
# Android (« J'ai un code d'abonnement ») : l'abonnement PASSE sur l'appli (l'appareil
# d'origine le perd). Comme une connexion a un compte achete ailleurs : rien ne s'achete
# dans l'appli (politique Paiements de Google Play). Sert aussi a changer de telephone.
CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"  # ni 0/O, ni 1/I/L : pas de confusion
TRANSFERTS_PAR_JOUR = 3
_code_lock = threading.Lock()


def normalize_code(code: str) -> str | None:
    """« k7p4 qx2m », « K7P4-QX2M »... -> « K7P4-QX2M » ; None si ce n'est pas un code valide."""
    brut = re.sub(r"[^A-Za-z0-9]", "", code or "").upper()
    if len(brut) != 8 or any(c not in CODE_ALPHABET for c in brut):
        return None
    return brut[:4] + "-" + brut[4:]


def subscription_code(device_id: str) -> str | None:
    """Code d'abonnement d'un appareil abonne (cree a la premiere demande) ; None sans
    abonnement actif date (les anciennes activations sans date ne se transferent pas)."""
    if not is_premium(device_id) or not get_premium_until(device_id):
        return None
    with _code_lock:
        conn = db.get_connection()
        try:
            row = conn.execute("SELECT code FROM subscription_codes WHERE device_id = ?", (device_id,)).fetchone()
            if row:
                return row[0]
            while True:
                brut = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
                code = brut[:4] + "-" + brut[4:]
                if conn.execute("INSERT OR IGNORE INTO subscription_codes (code, device_id, created) VALUES (?, ?, ?)",
                                (code, device_id, date.today().isoformat())).rowcount:
                    conn.commit()
                    return code
        finally:
            conn.close()


def transfer_by_code(code: str, device_id: str) -> dict:
    """Fait passer sur `device_id` l'abonnement du code. Les jours restants s'ajoutent a un
    abonnement deja actif sur cet appareil. Retourne {"ok": True, "premium_until", "code"}
    ou {"ok": False, "raison": "introuvable" | "expire" | "trop_de_transferts"}."""
    code = normalize_code(code)
    if not code:
        return {"ok": False, "raison": "introuvable"}
    with _code_lock:
        conn = db.get_connection()
        try:
            row = conn.execute("SELECT device_id, transfer_day, transfer_count FROM subscription_codes WHERE code = ?",
                               (code,)).fetchone()
        finally:
            conn.close()
        if not row:
            return {"ok": False, "raison": "introuvable"}
        origine, jour, nombre = row
        if origine == device_id:
            return {"ok": True, "premium_until": get_premium_until(device_id), "code": code, "deja": True}
        until = get_premium_until(origine) if is_premium(origine) else None
        if not until:
            return {"ok": False, "raison": "expire"}
        aujourdhui = date.today().isoformat()
        nombre = nombre if jour == aujourdhui else 0
        if nombre >= TRANSFERTS_PAR_JOUR:
            return {"ok": False, "raison": "trop_de_transferts"}
        jours = max(0, (date.fromisoformat(until) - date.today()).days)
        nouveau = extend_premium(device_id, jours)
        set_premium(origine, False)
        conn = db.get_connection()
        try:
            conn.execute("DELETE FROM subscription_codes WHERE device_id = ?", (device_id,))
            conn.execute("UPDATE subscription_codes SET device_id = ?, transfer_day = ?, transfer_count = ? WHERE code = ?",
                         (device_id, aujourdhui, nombre + 1, code))
            conn.commit()
        finally:
            conn.close()
    return {"ok": True, "premium_until": nouveau, "code": code}


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
