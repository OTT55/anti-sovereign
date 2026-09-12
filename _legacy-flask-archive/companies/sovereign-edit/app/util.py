"""Tiny shared helpers with no dependencies on the rest of the app."""

import uuid
from datetime import datetime, timezone

STEP_TYPES = [
    "Registration", "Capture", "Edit", "Colour Grade", "Sound", "VFX",
    "Master", "Release",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_work_id() -> str:
    return "SE-" + uuid.uuid4().hex[:10].upper()
