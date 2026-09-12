"""FrameVault's Provenance Engine — proving a creator made a thing.

The domain knowledge FrameVault owns: a **registration** is a signed claim that
a named creator made a specific piece of work at a specific time, and that the
claim has not been altered since.

The signature covers the **whole canonical record**, not just the file hash.
That distinction is the entire security property and was a real bug in the app
this is modelled on: signing only `hash|registry_id|created_at` meant a tampered
AI-disclosure still validated, so the one field a buyer most needs to trust was
the one field nobody was protecting.

Deterministic, standard-library only. HMAC-SHA256 with a per-installation
secret — the same shape the app already uses, so this is a port of a proven
mechanism rather than a new invention.
"""

import hashlib
import hmac
import json

#: Every field the signature covers. Adding a field here without re-signing
#: existing records invalidates them, which is correct: an unsigned field is an
#: unprotected one, and silently accepting it would be worse.
SIGNED_FIELDS = (
    "content_hash", "registry_id", "creator", "created_at",
    "title", "role", "contributors", "ai_disclosure", "source",
)


def content_hash(data):
    """SHA-256 of the work itself.

    Hashing happens wherever the file is — in the browser, in the app — so only
    the hash need ever travel. The work itself never has to leave the creator's
    machine to be registered, which is the point.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def canonical(record):
    """The exact bytes a signature is computed over.

    Sorted keys and no incidental whitespace, so the same record always
    produces the same bytes. Without that, re-serialising a record in a
    different key order would invalidate a perfectly good signature.
    """
    payload = {field: record.get(field, "") for field in SIGNED_FIELDS}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign(record, secret):
    """HMAC-SHA256 over the canonical record."""
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    return hmac.new(secret, canonical(record), hashlib.sha256).hexdigest()


def verify(record, signature, secret):
    """Is this record exactly what was signed?

    Compared with `compare_digest` rather than `==`. String comparison returns
    early on the first differing byte, which leaks how much of a forged
    signature was correct and lets an attacker rebuild it one byte at a time.
    """
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    expected = hmac.new(secret, canonical(record), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


class Registration:
    """One signed claim of authorship."""

    __slots__ = SIGNED_FIELDS + ("signature",)

    def __init__(self, **fields):
        for field in SIGNED_FIELDS:
            setattr(self, field, fields.get(field, ""))
        self.signature = fields.get("signature", "")

    def as_record(self):
        return {field: getattr(self, field) for field in SIGNED_FIELDS}

    def describe(self):
        return f"{self.title or 'untitled'} by {self.creator} ({self.registry_id})"

    def __repr__(self):
        return f"<Registration {self.describe()}>"


class Verdict:
    """What verification concluded, and why.

    Three outcomes rather than a boolean, because "we have never seen this
    work" and "we have seen it and it has been altered" are completely
    different messages to show someone, and collapsing them into `False` throws
    away the distinction that matters most.
    """

    __slots__ = ("status", "registration", "reason")

    def __init__(self, status, registration=None, reason=""):
        self.status = status          # "registered" | "altered" | "unknown"
        self.registration = registration
        self.reason = reason

    @property
    def is_authentic(self):
        return self.status == "registered"

    def describe(self):
        return f"{self.status}: {self.reason}"

    def __repr__(self):
        return f"<Verdict {self.describe()}>"
