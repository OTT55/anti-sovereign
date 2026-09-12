"""
The one place that talks to the database.

Keeping every query behind this module is the seam that makes the future
SQLite -> PostgreSQL swap (ADR 0002) a small change instead of a repo-wide hunt.
"""

import sqlite3

from flask import current_app, g

from .util import now_iso


def get_db() -> sqlite3.Connection:
    """One connection per request, stashed on Flask's request context."""
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


def init_db(app) -> None:
    """Create the schema (idempotent) and seed the V1 owner. Safe every startup."""
    conn = sqlite3.connect(app.config["DB_PATH"])
    conn.row_factory = sqlite3.Row
    try:
        with open(app.config["SCHEMA_PATH"], "r", encoding="utf-8") as fh:
            conn.executescript(fh.read())
        exists = conn.execute(
            "SELECT 1 FROM creators WHERE handle = ?", (app.config["OWNER_HANDLE"],)
        ).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO creators (handle, display_name, created_at) VALUES (?, ?, ?)",
                (app.config["OWNER_HANDLE"], app.config["OWNER_NAME"], now_iso()),
            )
        conn.commit()
    finally:
        conn.close()


def get_owner(db) -> sqlite3.Row:
    """The seeded creator the app acts as under V1 stubbed auth."""
    return db.execute(
        "SELECT * FROM creators WHERE handle = ?", (current_app.config["OWNER_HANDLE"],)
    ).fetchone()
