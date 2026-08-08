"""
Clearpath configuration.

Everything here is read from the environment where it matters, so nothing
sensitive is baked into the source. Sensible local defaults let the app run
with zero setup for development.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    APP_NAME = "Clearpath"

    # Where the SQLite database file lives. Override with CLEARPATH_DB.
    DB_PATH = os.environ.get("CLEARPATH_DB", str(BASE_DIR / "clearpath.db"))
    SCHEMA_PATH = str(BASE_DIR / "schema.sql")

    # The active rule pack + the reference data it depends on. Swapping which
    # pack is live is an environment change, not a code change — see
    # decisions/0002 and PRODUCTION-PLAN.md Phase 3 (additional rule packs).
    RULEPACK_PATH = Path(os.environ.get("CLEARPATH_RULEPACK", str(BASE_DIR / "rulepacks" / "core.json")))
    REFDATA_DIR = Path(os.environ.get("CLEARPATH_REFDATA_DIR", str(BASE_DIR / "refdata")))

    DEBUG = os.environ.get("CLEARPATH_DEBUG", "0") == "1"

    # PORTS.md: Clearpath owns 5104 in the Sovereign Stack's 51xx block.
    PORT = int(os.environ.get("CLEARPATH_PORT", "5104"))
    HOST = os.environ.get("HOST", "127.0.0.1")
