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
CREATE TABLE IF NOT EXISTS activation_requests (
    request_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    days INTEGER NOT NULL,
    nom TEXT,
    contact TEXT,
    ts TEXT NOT NULL,
    premium_until TEXT
);
CREATE TABLE IF NOT EXISTS funnel_events (
    device_id TEXT NOT NULL,
    etape TEXT NOT NULL,
    ts TEXT NOT NULL,
    plateforme TEXT,
    PRIMARY KEY (device_id, etape)
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


def _migrate_premium_until(conn: sqlite3.Connection) -> None:
    """Ajoute les colonnes premium_until (date d'expiration) et contact
    (numero WhatsApp de l'eleve, connu de l'admin puisqu'il recoit la preuve
    de paiement par ce canal - sert aux rappels avant expiration) si elles
    n'existent pas encore."""
    cols = [row[1] for row in conn.execute("PRAGMA table_info(subscriptions)").fetchall()]
    if "premium_until" not in cols:
        conn.execute("ALTER TABLE subscriptions ADD COLUMN premium_until TEXT")
        conn.commit()
    if "contact" not in cols:
        conn.execute("ALTER TABLE subscriptions ADD COLUMN contact TEXT")
        conn.commit()


def _migrate_usage_offre(conn: sqlite3.Connection) -> None:
    """Colonne offre ("gratuit"/"premium") du journal des couts IA, pour le
    plafond mensuel du gratuit, et index sur la date (somme du mois a chaque
    question)."""
    cols = [row[1] for row in conn.execute("PRAGMA table_info(usage_log)").fetchall()]
    if "offre" not in cols:
        try:
            conn.execute("ALTER TABLE usage_log ADD COLUMN offre TEXT")
        except sqlite3.OperationalError:
            pass  # deja ajoutee par l'autre worker Gunicorn
    conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_ts ON usage_log(ts)")
    conn.commit()


def _migrate_funnel_backfill(conn: sqlite3.Connection) -> None:
    """Donne une seule fois aux appareils deja connus leurs etapes passees de
    l'entonnoir (dates estimees d'apres leur activite) : sans cela, leur
    prochaine ouverture les compterait comme de nouvelles installations dans
    la cohorte du jour. Les cles du compteur qui ne sont pas des appareils
    (adresses IP du garde-fou, plafond premium) sont exclues."""
    already = conn.execute("SELECT 1 FROM _migrations WHERE name = 'funnel_backfill_v1'").fetchone()
    if already:
        return
    conn.execute(
        "INSERT OR IGNORE INTO funnel_events (device_id, etape, ts) "
        "SELECT device_id, 'ouverture', MIN(ts) FROM ("
        "  SELECT device_id, ts FROM progress_events"
        "  UNION ALL SELECT device_id, date FROM quota WHERE device_id LIKE 'dev-%'"
        "  UNION ALL SELECT device_id, updated FROM subscriptions WHERE updated IS NOT NULL"
        ") GROUP BY device_id"
    )
    conn.execute(
        "INSERT OR IGNORE INTO funnel_events (device_id, etape, ts) "
        "SELECT device_id, 'premiere_question', MIN(ts) FROM ("
        "  SELECT device_id, ts FROM progress_events WHERE type IN ('ask', 'quiz', 'correction')"
        "  UNION ALL SELECT device_id, date FROM quota WHERE device_id LIKE 'dev-%'"
        ") GROUP BY device_id"
    )
    conn.execute(
        "INSERT OR IGNORE INTO funnel_events (device_id, etape, ts) "
        "SELECT device_id, 'paiement', updated FROM subscriptions "
        "WHERE (premium = 1 OR premium_until IS NOT NULL) AND updated IS NOT NULL"
    )
    # OR IGNORE : deux workers Gunicorn peuvent faire cette migration en meme temps.
    conn.execute("INSERT OR IGNORE INTO _migrations (name) VALUES ('funnel_backfill_v1')")
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
                _migrate_premium_until(conn)
                _migrate_usage_offre(conn)
                _migrate_funnel_backfill(conn)
                _initialized = True
    return conn
