"""
The hash-chained audit log. Each entry commits to the hash of the entry
before it, so altering or deleting any past decision changes its hash and
breaks every link after it — unchanged mechanism from the MVP, just now
storing which ruleset decided the case alongside it.
"""

import hashlib
import json


def canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def append_entry(db, case_id: str, created_at: str, ruleset_id: int, payload: dict) -> tuple[str, str]:
    last = db.execute("SELECT entry_hash FROM audit ORDER BY id DESC LIMIT 1").fetchone()
    prev_hash = last["entry_hash"] if last else "0" * 64
    body = canonical(payload)
    entry_hash = hashlib.sha256((prev_hash + body).encode()).hexdigest()
    db.execute(
        "INSERT INTO audit (case_id, created_at, ruleset_id, payload, prev_hash, entry_hash) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (case_id, created_at, ruleset_id, body, prev_hash, entry_hash),
    )
    db.commit()
    return prev_hash, entry_hash


def verify_chain(entries_oldest_first: list) -> bool:
    """entries_oldest_first: rows with `payload` already parsed back to a dict."""
    prev = "0" * 64
    for e in entries_oldest_first:
        body = canonical(e["payload"])
        if e["prev_hash"] != prev or hashlib.sha256((prev + body).encode()).hexdigest() != e["entry_hash"]:
            return False
        prev = e["entry_hash"]
    return True
