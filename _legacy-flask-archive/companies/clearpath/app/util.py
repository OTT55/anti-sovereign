"""Tiny shared helpers with no dependencies on the rest of the app."""

import uuid
from datetime import datetime, timezone


def now_iso() -> str:
    """Current time as a UTC ISO-8601 string (the format we store timestamps in)."""
    return datetime.now(timezone.utc).isoformat()


def new_case_id() -> str:
    """A short, friendly public id for a routed case, e.g. CP-AB12CD34EF56."""
    return "CP-" + uuid.uuid4().hex[:12].upper()
