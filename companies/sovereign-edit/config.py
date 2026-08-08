"""
Sovereign Edit configuration. Read from the environment where it matters;
sensible local defaults so it runs with zero setup.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    DB_PATH = os.environ.get("SOVEREIGN_EDIT_DB", str(BASE_DIR / "sovereign_edit.db"))
    SCHEMA_PATH = str(BASE_DIR / "schema.sql")
    DEBUG = os.environ.get("SOVEREIGN_EDIT_DEBUG", "0") == "1"

    # Sovereign Stack owns the 5100-5199 block; CreativeOS owns 5000-5099.
    # See PORTS.md at the repo root — the shared registry across sessions.
    PORT = int(os.environ.get("SOVEREIGN_EDIT_PORT", "5105"))

    # Loopback-only by default; set HOST=0.0.0.0 to reach this from another
    # device on the same network (see scripts/run_for_phone.py).
    HOST = os.environ.get("HOST", "127.0.0.1")

    APP_NAME = "Sovereign Edit"
