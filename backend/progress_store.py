"""Journal de progression par eleve (device_id) et notes de profil (issues du
diagnostic initial) qui personnalisent les futures explications. Stockage :
SQLite partage (voir db.py).
"""
from datetime import datetime, timezone

import db


def log_event(device_id: str, event_type: str, pays: str, niveau: str, matiere: str,
              score: int | None = None, total: int | None = None) -> None:
    """event_type: 'ask' | 'quiz' | 'diagnostic' | 'correction'"""
    try:
        conn = db.get_connection()
        try:
            conn.execute(
                "INSERT INTO progress_events (ts, device_id, type, pays, niveau, matiere, score, total) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), device_id, event_type,
                 pays, niveau, matiere, score, total),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass  # le suivi ne doit jamais faire echouer une reponse a l'eleve


def get_progress(device_id: str) -> dict:
    """Agrege l'activite d'un eleve par matiere : nb de questions, score moyen
    aux quiz/diagnostics/corrections, derniere activite."""
    conn = db.get_connection()
    try:
        rows = conn.execute(
            "SELECT type, matiere, score, total, ts FROM progress_events WHERE device_id = ?",
            (device_id,),
        ).fetchall()
    finally:
        conn.close()

    by_matiere: dict[str, dict] = {}
    for event_type, m, score, total, ts in rows:
        m = m or "?"
        bucket = by_matiere.setdefault(m, {
            "matiere": m, "questions": 0, "quiz_scores": [], "last_activity": None,
        })
        if event_type == "ask":
            bucket["questions"] += 1
        elif event_type in ("quiz", "diagnostic", "correction") and total:
            bucket["quiz_scores"].append(score / total)
        if not bucket["last_activity"] or ts > bucket["last_activity"]:
            bucket["last_activity"] = ts

    result = []
    for m, bucket in by_matiere.items():
        scores = bucket["quiz_scores"]
        avg = round(100 * sum(scores) / len(scores)) if scores else None
        result.append({
            "matiere": m,
            "questions": bucket["questions"],
            "quiz_count": len(scores),
            "avg_score_pct": avg,
            "last_activity": bucket["last_activity"],
        })
    result.sort(key=lambda r: r["last_activity"] or "", reverse=True)
    return {"matieres": result}


def set_profile_note(device_id: str, matiere: str, note: str) -> None:
    conn = db.get_connection()
    try:
        conn.execute(
            "INSERT INTO profiles (device_id, matiere, note) VALUES (?, ?, ?) "
            "ON CONFLICT(device_id, matiere) DO UPDATE SET note=excluded.note",
            (device_id, matiere, note),
        )
        conn.commit()
    finally:
        conn.close()


def get_profile_note(device_id: str, matiere: str) -> str | None:
    conn = db.get_connection()
    try:
        row = conn.execute(
            "SELECT note FROM profiles WHERE device_id = ? AND matiere = ?",
            (device_id, matiere),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()
