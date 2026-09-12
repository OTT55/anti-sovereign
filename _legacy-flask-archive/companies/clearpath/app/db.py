"""
The one place that talks to the database, plus resolving which ruleset
version is active on boot. Keeping every query behind this module is the
seam that makes a future SQLite -> PostgreSQL swap a small change instead of
a repo-wide hunt (same seam Canonchain uses).
"""

import sqlite3

from flask import current_app, g

from .rules import LoadedRuleset, load_ruleset
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
    """Create the schema (idempotent) and register the active ruleset. Safe
    every startup — stashes the resolved ruleset on app.config so every
    request evaluates against the same in-memory copy the DB row records."""
    conn = sqlite3.connect(app.config["DB_PATH"])
    conn.row_factory = sqlite3.Row
    try:
        with open(app.config["SCHEMA_PATH"], "r", encoding="utf-8") as fh:
            conn.executescript(fh.read())
        loaded = load_ruleset(app.config["RULEPACK_PATH"], app.config["REFDATA_DIR"])
        app.config["RULESET_ID"] = _register_ruleset(conn, loaded)
        app.config["RULESET"] = loaded
        conn.commit()
    finally:
        conn.close()


def _register_ruleset(conn: sqlite3.Connection, loaded: LoadedRuleset) -> int:
    row = conn.execute(
        "SELECT id, content_hash FROM rulesets WHERE pack = ? AND version = ?",
        (loaded.pack, loaded.version),
    ).fetchone()
    if row is not None:
        if row["content_hash"] != loaded.content_hash:
            # A ruleset version is a promise: every past decision that names
            # this id can be replayed against exactly these rules, forever.
            # Editing the JSON in place without bumping the version would
            # silently break that promise, so this fails loudly instead.
            raise RuntimeError(
                f"rulepacks/{loaded.pack}.json no longer matches the frozen copy already "
                f"stored for version {loaded.version} (ruleset id {row['id']}). "
                "Bump the version in the rule pack — a ruleset version is immutable "
                "once it has decided a case."
            )
        return row["id"]
    cur = conn.execute(
        "INSERT INTO rulesets (pack, version, content_hash, loaded_at, rules_json, refdata_json) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (loaded.pack, loaded.version, loaded.content_hash, now_iso(),
         loaded.rules_json, loaded.refdata_json),
    )
    return cur.lastrowid
