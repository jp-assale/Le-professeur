"""Journal du cout reel des appels IA, pour remplacer les hypotheses par des
vraies donnees. Stockage : SQLite partage (voir db.py).

Tarifs verifies le 2026-09-10 sur https://claude.com/pricing. Si le modele
utilise par l'app change, mets a jour PRICING_USD_PER_MTOK et revalide ces
tarifs (ils peuvent changer sans preavis).
"""
import os
import time
from datetime import datetime, timezone

import db

PRICING_USD_PER_MTOK = {
    # input / output en USD pour 1 million de tokens.
    "claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0},
    # Tarif des requetes de 100K tokens ou moins (0,50 / 2,50 au-dela, jamais
    # le cas ici). Verifie le 2026-10-14.
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50},
}
_DEFAULT_PRICING = {"input": 1.0, "output": 5.0}

# Budget mensuel IA choisi par l'utilisateur pour l'indicateur "presque epuise"
# de la page admin - purement indicatif, ne bloque rien automatiquement.
MONTHLY_BUDGET_USD = float(os.environ.get("ANTHROPIC_MONTHLY_BUDGET_USD", "85"))

# Plafond de depense IA du GRATUIT par mois (celui-ci bloque) : une fois
# atteint, les eleves non abonnes passent a FREE_LIMIT_OVER_BUDGET questions
# par jour jusqu'a la fin du mois. Les abonnes ne sont jamais concernes.
FREE_MONTHLY_BUDGET_USD = float(os.environ.get("FREE_MONTHLY_BUDGET_USD", "35"))


def log_call(model: str, endpoint: str, input_tokens: int, output_tokens: int,
             offre: str | None = None) -> None:
    """`offre` : "gratuit" ou "premium" (qui a pose la question)."""
    pricing = PRICING_USD_PER_MTOK.get(model, _DEFAULT_PRICING)
    cost_usd = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
    try:
        conn = db.get_connection()
        try:
            conn.execute(
                "INSERT INTO usage_log (ts, endpoint, model, input_tokens, output_tokens, cost_usd_est, offre) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), endpoint, model,
                 input_tokens, output_tokens, round(cost_usd, 6), offre),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass  # le suivi de cout ne doit jamais faire echouer une reponse a l'eleve


def summary() -> dict:
    """Petit resume utile pour verifier le cout reel apres usage (debug/admin)."""
    conn = db.get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(cost_usd_est), 0) FROM usage_log"
        ).fetchone()
        return {"calls": row[0], "total_cost_usd_est": round(row[1], 4)}
    finally:
        conn.close()


def month_cost_usd(offre: str | None = None) -> float:
    """Cout IA estime depuis le 1er du mois en cours (UTC). Avec
    offre="gratuit", seulement les questions des eleves non abonnes (les
    appels anterieurs a cette distinction sont comptes comme gratuits, par
    prudence)."""
    month_start = datetime.now(timezone.utc).strftime("%Y-%m-01")
    sql = "SELECT COALESCE(SUM(cost_usd_est), 0) FROM usage_log WHERE ts >= ?"
    if offre == "gratuit":
        sql += " AND (offre IS NULL OR offre = 'gratuit')"
    elif offre:
        sql += " AND offre = ?"
    params = (month_start, offre) if offre and offre != "gratuit" else (month_start,)
    conn = db.get_connection()
    try:
        row = conn.execute(sql, params).fetchone()
        return round(row[0], 4)
    finally:
        conn.close()


_cache_gratuit = {"valeur": 0.0, "expire": 0.0}


def free_budget_exceeded() -> bool:
    """Le plafond mensuel du gratuit est-il atteint ? Recalcule au plus une
    fois par minute et par processus (appele avant chaque question)."""
    if FREE_MONTHLY_BUDGET_USD <= 0:
        return False
    now = time.monotonic()
    if now >= _cache_gratuit["expire"]:
        _cache_gratuit["valeur"] = month_cost_usd("gratuit")
        _cache_gratuit["expire"] = now + 60
    return _cache_gratuit["valeur"] >= FREE_MONTHLY_BUDGET_USD
