"""Base de donnees SQLite partagee (remplace les fichiers JSON individuels
de quota_store/subscription/payments_store/usage_log/progress_store/reports).

Pourquoi : ces modules utilisaient chacun un fichier JSON + un
threading.Lock() en memoire. Ce verrou ne protege que les threads D'UN SEUL
processus - avec plusieurs workers Gunicorn (plusieurs processus separes),
deux requetes pouvaient lire le meme fichier JSON en meme temps et perdre
l'incrementation de l'une des deux (ex: quota mal compte). SQLite en mode
WAL gere correctement les acces concurrents de PLUSIEURS PROCESSUS sur la
MEME machine.

Limite qui reste : un seul fichier sur UNE seule machine. Si l'app doit un
jour tourner sur plusieurs machines en parallele (vraie montee en charge a
grande echelle), il faudra migrer vers un serveur de base de donnees
partage (Postgres) - mais passer par SQLite maintenant, avec du vrai SQL
plutot que des fichiers JSON ad hoc, rend cette migration future beaucoup
plus simple.
"""
import json
import os
import sqlite3
import threading

from paths import DATA_DIR

_DB_PATH = os.path.join(DATA_DIR, "app.db")
_INIT_LOCK = threading.Lock()
_initialized = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS quota (
    device_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS subscriptions (
    device_id TEXT PRIMARY KEY,
    premium INTEGER NOT NULL DEFAULT 0,
    updated TEXT
);
CREATE TABLE IF NOT EXISTS payments (
    transaction_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd_est REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS progress_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    device_id TEXT NOT NULL,
    type TEXT NOT NULL,
    pays TEXT,
    niveau TEXT,
    matiere TEXT,
    score INTEGER,
    total INTEGER
);
CREATE INDEX IF NOT EXISTS idx_progress_device ON progress_events(device_id);
CREATE TABLE IF NOT EXISTS profiles (
    device_id TEXT NOT NULL,
    matiere TEXT NOT NULL,
    note TEXT NOT NULL,
    PRIMARY KEY (device_id, matiere)
);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    device_id TEXT NOT NULL,
    context TEXT,
    excerpt TEXT,
    comment TEXT
);
CREATE TABLE IF NOT EXISTS _migrations (
    name TEXT PRIMARY KEY
);
"""


def _load_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _load_jsonl(path: str) -> list:
    if not os.path.exists(path):
        return []
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _migrate_legacy_json(conn: sqlite3.Connection) -> None:
    """Importe une seule fois les anciens fichiers JSON/JSONL s'ils existent.
    Idempotent (verifie _migrations avant de rejouer), et ne supprime jamais
    les fichiers d'origine - ils restent comme sauvegarde."""
    already = conn.execute("SELECT 1 FROM _migrations WHERE name = 'json_import_v1'").fetchone()
    if already:
        return

    quota = _load_json(os.path.join(DATA_DIR, "quota.json"))
    for device_id, entry in quota.items():
        conn.execute(
            "INSERT OR IGNORE INTO quota (device_id, date, count) VALUES (?, ?, ?)",
            (device_id, entry.get("date", ""), entry.get("count", 0)),
        )

    subs = _load_json(os.path.join(DATA_DIR, "subscriptions.json"))
    for device_id, entry in subs.items():
        conn.execute(
            "INSERT OR IGNORE INTO subscriptions (device_id, premium, updated) VALUES (?, ?, ?)",
            (device_id, int(bool(entry.get("premium"))), entry.get("updated")),
        )

    payments = _load_json(os.path.join(DATA_DIR, "payments.json"))
    for transaction_id, entry in payments.items():
        conn.execute(
            "INSERT OR IGNORE INTO payments (transaction_id, device_id, status, created) VALUES (?, ?, ?, ?)",
            (transaction_id, entry.get("device_id", ""), entry.get("status", "pending"), entry.get("created", "")),
        )

    for entry in _load_jsonl(os.path.join(DATA_DIR, "usage_log.jsonl")):
        conn.execute(
            "INSERT INTO usage_log (ts, endpoint, model, input_tokens, output_tokens, cost_usd_est) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (entry.get("ts", ""), entry.get("endpoint", ""), entry.get("model", ""),
             entry.get("input_tokens", 0), entry.get("output_tokens", 0), entry.get("cost_usd_est", 0)),
        )

    for entry in _load_jsonl(os.path.join(DATA_DIR, "progress.jsonl")):
        conn.execute(
            "INSERT INTO progress_events (ts, device_id, type, pays, niveau, matiere, score, total) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (entry.get("ts", ""), entry.get("device_id", ""), entry.get("type", ""),
             entry.get("pays"), entry.get("niveau"), entry.get("matiere"),
             entry.get("score"), entry.get("total")),
        )

    profiles = _load_json(os.path.join(DATA_DIR, "profiles.json"))
    for device_id, by_matiere in profiles.items():
        for matiere, note in by_matiere.items():
            conn.execute(
                "INSERT OR IGNORE INTO profiles (device_id, matiere, note) VALUES (?, ?, ?)",
                (device_id, matiere, note),
            )

    for entry in _load_jsonl(os.path.join(DATA_DIR, "reports.jsonl")):
        conn.execute(
            "INSERT INTO reports (ts, device_id, context, excerpt, comment) VALUES (?, ?, ?, ?, ?)",
            (entry.get("ts", ""), entry.get("device_id", ""), entry.get("context", ""),
             entry.get("excerpt", ""), entry.get("comment", "")),
        )

    conn.execute("INSERT INTO _migrations (name) VALUES ('json_import_v1')")
    conn.commit()


def get_connection() -> sqlite3.Connection:
    global _initialized
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    if not _initialized:
        with _INIT_LOCK:
            if not _initialized:
                conn.executescript(SCHEMA)
                conn.commit()
                _migrate_legacy_json(conn)
                _initialized = True
    return conn
