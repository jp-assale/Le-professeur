"""Correspondance transaction_id -> device_id pour retrouver qui payer une
fois que CinetPay confirme une transaction (le webhook ne renvoie que le
transaction_id, pas le device_id). Stockage : SQLite partage (voir db.py)."""
import uuid
from datetime import datetime, timezone

import db


def create_transaction(device_id: str) -> str:
    transaction_id = "sub-" + uuid.uuid4().hex[:20]
    conn = db.get_connection()
    try:
        conn.execute(
            "INSERT INTO payments (transaction_id, device_id, status, created) VALUES (?, ?, 'pending', ?)",
            (transaction_id, device_id, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
    return transaction_id


def get_device_id(transaction_id: str) -> str | None:
    conn = db.get_connection()
    try:
        row = conn.execute(
            "SELECT device_id FROM payments WHERE transaction_id = ?", (transaction_id,)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def mark_status(transaction_id: str, status: str) -> None:
    conn = db.get_connection()
    try:
        conn.execute("UPDATE payments SET status = ? WHERE transaction_id = ?", (status, transaction_id))
        conn.commit()
    finally:
        conn.close()
