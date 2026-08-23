"""Journal local du cout reel des appels IA, pour remplacer les hypotheses par
des vraies donnees (faiblesse #4 : economie du service non verifiee).

Tarifs approximatifs UNIQUEMENT - A VERIFIER sur https://www.anthropic.com/pricing
avant de t'en servir pour une decision business. Mets a jour PRICING_USD_PER_MTOK
si le modele ou les tarifs changent.
"""
import json
import os
import threading
from datetime import datetime, timezone

from paths import DATA_DIR

_LOCK = threading.Lock()
_LOG_PATH = os.path.join(DATA_DIR, "usage_log.jsonl")

PRICING_USD_PER_MTOK = {
    # input / output en USD pour 1 million de tokens - VALEURS APPROXIMATIVES.
    "claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0},
}
_DEFAULT_PRICING = {"input": 1.0, "output": 5.0}


def log_call(model: str, endpoint: str, input_tokens: int, output_tokens: int) -> None:
    pricing = PRICING_USD_PER_MTOK.get(model, _DEFAULT_PRICING)
    cost_usd = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd_est": round(cost_usd, 6),
    }
    try:
        with _LOCK:
            with open(_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass  # le suivi de cout ne doit jamais faire echouer une reponse a l'eleve


def summary() -> dict:
    """Petit resume utile pour verifier le cout reel apres usage (debug/admin)."""
    if not os.path.exists(_LOG_PATH):
        return {"calls": 0, "total_cost_usd_est": 0.0}
    total_cost = 0.0
    calls = 0
    with open(_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            total_cost += entry.get("cost_usd_est", 0)
            calls += 1
    return {"calls": calls, "total_cost_usd_est": round(total_cost, 4)}
