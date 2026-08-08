"""
Veridact configuration. Read from the environment where it matters; sensible
local defaults so it runs with zero setup.

Note: unlike the MVP, Veridact holds NO signing secret — devices sign, Veridact
only verifies with public keys. So there is nothing sensitive to protect here.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    DB_PATH = os.environ.get("VERIDACT_DB", str(BASE_DIR / "veridact.db"))
    SCHEMA_PATH = str(BASE_DIR / "schema.sql")
    DEBUG = os.environ.get("VERIDACT_DEBUG", "0") == "1"

    # Sovereign Stack owns the 5100-5199 block; CreativeOS owns 5000-5099.
    # See PORTS.md at the repo root — the shared registry across sessions.
    PORT = int(os.environ.get("VERIDACT_PORT", "5102"))

    APP_NAME = "Veridact"

    # getUserMedia (the camera) requires a "secure context": HTTPS, or the
    # literal hostname localhost/127.0.0.1. A phone on the same Wi-Fi reaching
    # this machine by its LAN IP is NOT localhost, so testing with a real phone
    # camera needs HTTPS even for a throwaway local test. VERIDACT_HTTPS=1
    # turns on an ad-hoc, auto-generated self-signed certificate (via
    # pyOpenSSL) — good enough for this, never for a real deployment.
    HTTPS = os.environ.get("VERIDACT_HTTPS", "0") == "1"
    # 0.0.0.0 binds every network interface, not just loopback, so a phone on
    # the same LAN can reach it. Only meaningful together with HTTPS above.
    HOST = os.environ.get("VERIDACT_HOST", "127.0.0.1")
