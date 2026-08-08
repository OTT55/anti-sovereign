"""Tiny shared helpers with no dependencies on the rest of the app."""

import uuid
from datetime import datetime, timezone


def now_iso() -> str:
    """Current time as a UTC ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def new_manifest_id() -> str:
    """A short, friendly public id for a manifest, e.g. VD-AB12CD34EF56."""
    return "VD-" + uuid.uuid4().hex[:12].upper()
