"""Stable, readable identifiers and a single source of truth for record time.

Every timestamp in the graph must come from `now()`. Record-time queries
compare ISO strings lexicographically, which is only valid because every value
is UTC in the same format — see the note in `store.py`.
"""

import uuid
from datetime import datetime, timezone

SPACE = "SPC"
ENTITY = "ENT"
ASSERTION = "ASR"


def new_id(prefix):
    """e.g. ENT-9F3A2B7C41. Readable in logs and diffs, unlike a bare UUID."""
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


def now():
    return datetime.now(timezone.utc).isoformat()
