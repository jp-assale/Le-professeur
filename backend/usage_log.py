"""Journal du cout reel des appels IA, pour remplacer les hypotheses par des
vraies donnees. Stockage : SQLite partage (voir db.py).

Tarifs approximatifs UNIQUEMENT - A VERIFIER sur https://www.anthropic.com/pricing
avant de t'en servir pour une decision business. Mets a jour PRICING_USD_PER_MTOK
si le modele ou les tarifs changent.
"""
from datetime import datetime, timezone

import db

PRICING_USD_PER_MTOK = {
    # input / output en USD pour 1 million de tokens - VALEURS APPROXIMATIVES.
    "claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0},
}
_DEFAULT_PRICING = {"input": 1.0, "output": 5.0}


def log_call(model: str, endpoint: str, input_tokens: int, output_tokens: int) -> None:
    pricing = PRICING_USD_PER_MTOK.get(model, _DEFAULT_PRICING)
    cost_usd = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
    try:
        conn = db.get_connection()
        try:
            conn.execute(
                "INSERT INTO usage_log (ts, endpoint, model, input_tokens, output_tokens, cost_usd_est) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), endpoint, model,
                 input_tokens, output_tokens, round(cost_usd, 6)),
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
