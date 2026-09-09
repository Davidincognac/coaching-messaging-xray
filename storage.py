import os
import secrets
import sqlite3
from datetime import datetime

# Render injects RENDER=true into the environment automatically.
# Locally the variable is absent, so we fall back to the project directory.
_HERE = os.path.dirname(os.path.abspath(__file__))

def _pick_db_path():
    """On Render the DB lives on the persistent disk at /var/data. If that disk is ever missing,
    detached, or unwritable, fall back to the app directory with a loud warning INSTEAD of
    crashing at import (which used to 502 the whole site). Degraded mode means audits saved now
    do not survive a redeploy — the site itself stays up."""
    if os.getenv("RENDER"):
        try:
            os.makedirs("/var/data", exist_ok=True)
            probe = sqlite3.connect("/var/data/pipeline.db")
            probe.close()
            return "/var/data/pipeline.db"
        except Exception as e:
            print(f"[storage] WARNING: /var/data unavailable ({e}); using the app directory. "
                  "Audits saved now will NOT survive a redeploy.", flush=True)
    return os.path.join(_HERE, "pipeline.db")

DB_PATH = _pick_db_path()


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audits (
                domain          TEXT PRIMARY KEY,
                first_name      TEXT NOT NULL DEFAULT '',
                email           TEXT NOT NULL DEFAULT '',
                headline        TEXT NOT NULL DEFAULT '',
                score           TEXT NOT NULL DEFAULT '',
                tokens          TEXT NOT NULL DEFAULT '',
                screenshot_path TEXT NOT NULL DEFAULT '',
                raw_json        TEXT NOT NULL DEFAULT '',
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            )
        """)
        conn.commit()


def save_audit(
    domain,
    first_name="",
    email="",
    headline="",
    score="",
    tokens="",
    screenshot_path="",
    raw_json="",
):
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO audits
                (domain, first_name, email, headline, score, tokens,
                 screenshot_path, raw_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(domain) DO UPDATE SET
                first_name      = excluded.first_name,
                email           = excluded.email,
                headline        = excluded.headline,
                score           = excluded.score,
                tokens          = excluded.tokens,
                screenshot_path = excluded.screenshot_path,
                raw_json        = excluded.raw_json,
                updated_at      = excluded.updated_at
            """,
            (
                domain,
                first_name,
                email,
                headline,
                score,
                tokens,
                screenshot_path,
                raw_json,
                now,
                now,
            ),
        )
        conn.commit()


def get_audit(domain):
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM audits WHERE domain = ?", (domain,)
        ).fetchone()
    return dict(row) if row else None


def init_leads():
    """The Buying Triggers opt-in. Kept in our own DB as well as MailerLite, so a lead is never lost
    to a failed API call, and so we can see which markets coaches actually ask for."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trigger_leads (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                token       TEXT NOT NULL DEFAULT '',
                email       TEXT NOT NULL,
                first_name  TEXT NOT NULL DEFAULT '',
                last_name   TEXT NOT NULL DEFAULT '',
                niche_typed TEXT NOT NULL DEFAULT '',
                niche_match TEXT NOT NULL DEFAULT '',
                sent        INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trigger_leads_email ON trigger_leads(email)")
        # A table created before tokens existed has no such column. Add it rather than lose the rows.
        cols = {r[1] for r in conn.execute("PRAGMA table_info(trigger_leads)")}
        if "token" not in cols:
            conn.execute("ALTER TABLE trigger_leads ADD COLUMN token TEXT NOT NULL DEFAULT ''")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_trigger_leads_token "
                     "ON trigger_leads(token) WHERE token != ''")
        conn.commit()


def save_trigger_lead(email, first_name="", last_name="", niche_typed="", niche_match=""):
    """One row per submission. Deliberately NOT deduped on email: a coach asking twice, or asking for
    a second market, is a real signal we want to keep.

    Returns the row's TOKEN, not its id. The token is what travels in a link to the next step, so a
    coach who has already told us their name, email and niche never has to type any of it again. An
    id would work too, but a guessable one lets anyone walk through other people's records.
    """
    now = datetime.utcnow().isoformat()
    token = secrets.token_urlsafe(16)
    with _connect() as conn:
        conn.execute(
            """INSERT INTO trigger_leads
                   (token, email, first_name, last_name, niche_typed, niche_match, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (token, email, first_name, last_name, niche_typed, niche_match, now),
        )
        conn.commit()
    return token


def get_trigger_lead(token):
    """The lead behind a token, or None. This is how a later step knows who it is talking to."""
    if not token:
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM trigger_leads WHERE token = ?", (token,)
        ).fetchone()
    return dict(row) if row else None


def trigger_leads(limit=200):
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM trigger_leads ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# Initialise on import — table exists before any route touches it.
init_db()
init_leads()
