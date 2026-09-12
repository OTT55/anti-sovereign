"""The one place that talks to the database (the SQLite->Postgres seam)."""

import sqlite3

from flask import current_app, g


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(current_app.config["DB_PATH"])
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


def close_db(_exc=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _add_column_if_missing(conn, table, column, ddl) -> None:
    """CREATE TABLE IF NOT EXISTS won't add a column to a table that already
    exists — a database created before decisions/0004 needs this migration."""
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_db(app) -> None:
    """Create the schema (idempotent) and migrate older databases. Safe every startup."""
    conn = sqlite3.connect(app.config["DB_PATH"])
    try:
        with open(app.config["SCHEMA_PATH"], "r", encoding="utf-8") as fh:
            conn.executescript(fh.read())
        # decisions/0004: ECDSA P-256 support, added after the original schema.
        _add_column_if_missing(conn, "devices", "algorithm", "algorithm TEXT NOT NULL DEFAULT 'schnorr'")
        _add_column_if_missing(conn, "manifests", "sig_algorithm", "sig_algorithm TEXT NOT NULL DEFAULT 'schnorr'")
        # decisions/0009: soft-binding watermark secret, added after the original schema.
        _add_column_if_missing(conn, "manifests", "watermark_secret", "watermark_secret TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_manifest_watermark ON manifests(watermark_secret)")
        conn.commit()
    finally:
        conn.close()
