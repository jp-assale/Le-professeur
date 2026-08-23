"""Correspondance transaction_id -> device_id pour retrouver qui payer une
fois que CinetPay confirme une transaction (le webhook ne renvoie que le
transaction_id, pas le device_id)."""
import json
import os
import threading
import uuid
from datetime import datetime, timezone

from paths import DATA_DIR

_LOCK = threading.Lock()
_STORE_PATH = os.path.join(DATA_DIR, "payments.json")


def _load() -> dict:
    if not os.path.exists(_STORE_PATH):
        return {}
    with open(_STORE_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save(data: dict) -> None:
    with open(_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)


def create_transaction(device_id: str) -> str:
    transaction_id = "sub-" + uuid.uuid4().hex[:20]
    with _LOCK:
        data = _load()
        data[transaction_id] = {
            "device_id": device_id,
            "status": "pending",
            "created": datetime.now(timezone.utc).isoformat(),
        }
        _save(data)
    return transaction_id


def get_device_id(transaction_id: str) -> str | None:
    entry = _load().get(transaction_id)
    return entry.get("device_id") if entry else None


def mark_status(transaction_id: str, status: str) -> None:
    with _LOCK:
        data = _load()
        if transaction_id in data:
            data[transaction_id]["status"] = status
            _save(data)
