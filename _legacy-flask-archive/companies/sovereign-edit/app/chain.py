"""
The hash chain: how Sovereign Edit makes a film's history tamper-evident.

Every production step is a block. Each block commits to the hash of the block
before it:

    block_hash = SHA-256(prev_hash + canonical(step fields))

Because each block's hash feeds the next block's `prev_hash`, changing anything
about a past step (who graded it, which file it produced, when) changes that
block's hash and breaks every link after it. The last block's hash is the work's
**lineage hash** — one fingerprint of its entire authenticated history.

Pure functions only — no Flask, no database. That makes this file testable on its
own and keeps the trust-critical logic in one readable place.
"""

import hashlib
import json

GENESIS = "0" * 64


def step_fields(row) -> dict:
    """The exact fields a block commits to.

    `is_master` is deliberately NOT here: the chain records what *happened*
    (immutable), while which cut is the approved master is a decision you may
    revisit. See decisions/0002.
    """
    return {
        "work_id": row["work_id"],
        "seq": row["seq"],
        "step_type": row["step_type"],
        "actor": row["actor"],
        "tool": row["tool"] or "",
        "notes": row["notes"] or "",
        "filename": row["filename"] or "",
        "file_hash": row["file_hash"] or "",
        "created_at": row["created_at"],
    }


def block_hash(prev_hash: str, fields: dict) -> str:
    body = json.dumps(fields, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((prev_hash + body).encode()).hexdigest()


def verify_chain(steps) -> tuple[bool, int | None]:
    """Recompute the whole chain.

    Returns (intact, first_broken_seq). If a step was altered we report exactly
    where the lineage stops being trustworthy, rather than a bare yes/no.
    """
    prev = GENESIS
    for s in steps:
        expected = block_hash(prev, step_fields(s))
        if s["prev_hash"] != prev or s["block_hash"] != expected:
            return False, s["seq"]
        prev = s["block_hash"]
    return True, None


def lineage_hash(steps) -> str | None:
    """The final block's hash — one fingerprint of the work's whole history."""
    return steps[-1]["block_hash"] if steps else None
