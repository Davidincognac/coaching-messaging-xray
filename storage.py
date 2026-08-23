import os
import sqlite3
from datetime import datetime

# Render injects RENDER=true into the environment automatically.
# Locally the variable is absent, so we fall back to the project directory.
DB_PATH = (
    "/var/data/pipeline.db"
    if os.getenv("RENDER")
    else os.path.join(os.path.dirname(os.path.abspath(__file__)), "pipeline.db")
)


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


# Initialise on import — table exists before any route touches it.
init_db()
