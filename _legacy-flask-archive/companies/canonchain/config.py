"""
Canonchain configuration.

Everything here is read from the environment where it matters, so nothing
sensitive is baked into the source. Sensible local defaults let the app run with
zero setup for development.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    # Where the SQLite database file lives. Override with CANONCHAIN_DB (and point
    # it at a Postgres URL + a different db.py when we make that swap).
    DB_PATH = os.environ.get("CANONCHAIN_DB", str(BASE_DIR / "canonchain.db"))

    # The database shape (ADR 0002).
    SCHEMA_PATH = str(BASE_DIR / "schema.sql")

    # The HMAC signing secret. In production set CANONCHAIN_SECRET (a hex string).
    # For local dev, if it's unset we generate one once and cache it in this
    # gitignored file so signatures stay stable across restarts.
    SECRET_ENV = os.environ.get("CANONCHAIN_SECRET")
    SECRET_FILE = str(BASE_DIR / ".canonchain_secret")

    # Debug reloader/traceback. Off by default in anything but explicit dev.
    DEBUG = os.environ.get("CANONCHAIN_DEBUG", "0") == "1"

    PORT = int(os.environ.get("CANONCHAIN_PORT", "5101"))

    # Loopback-only by default; set HOST=0.0.0.0 to reach this from another
    # device on the same network (see scripts/run_for_phone.py).
    HOST = os.environ.get("HOST", "127.0.0.1")

    # V1 auth is stubbed: the app operates as this seeded creator until real
    # sign-in is switched on. The data model is already multi-user (ADR 0002).
    OWNER_HANDLE = os.environ.get("CANONCHAIN_OWNER", "ott")
    OWNER_NAME = os.environ.get("CANONCHAIN_OWNER_NAME", "OTT")
