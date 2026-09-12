"""
The one place that talks to the database.

Keeping every query behind this module is the seam that makes a future
SQLite -> PostgreSQL swap a small change instead of a repo-wide hunt.
"""

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


def init_db(app) -> None:
    """Create the schema (idempotent). Safe to call on every startup."""
    conn = sqlite3.connect(app.config["DB_PATH"])
    try:
        with open(app.config["SCHEMA_PATH"], "r", encoding="utf-8") as fh:
            conn.executescript(fh.read())
        conn.commit()
    finally:
        conn.close()
