"""
The registry brain: the Merkle-tree math and the register/verify operations.

Deliberately free of web code so it can be tested on its own (Phase 4). Web and
API layers call into here; this module never imports Flask request/response.

Merkle recap: every registration's hash is a leaf. Pairs of hashes are hashed
together up the tree to a single root. An inclusion proof is the short list of
sibling hashes needed to recompute the root from one leaf — anyone can check it
without trusting the server.
"""

import hashlib
import re

from .signing import sign_registration
from .util import new_registry_id, now_iso

SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


# --------------------------------------------------------------------------
# Merkle tree (pure functions)
# --------------------------------------------------------------------------

def _h(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def _pair(left: str, right: str) -> str:
    return _h(left + right)


def merkle_root(leaves: list[str]) -> str | None:
    if not leaves:
        return None
    level = list(leaves)
    while len(level) > 1:
        level = [
            _pair(level[i], level[i + 1] if i + 1 < len(level) else level[i])
            for i in range(0, len(level), 2)
        ]
    return level[0]


def merkle_proof(leaves: list[str], index: int) -> list[dict]:
    proof, level, idx = [], list(leaves), index
    while len(level) > 1:
        nxt = [
            _pair(level[i], level[i + 1] if i + 1 < len(level) else level[i])
            for i in range(0, len(level), 2)
        ]
        if idx % 2 == 0:
            sib = level[idx + 1] if idx + 1 < len(level) else level[idx]
            proof.append({"position": "right", "hash": sib})
        else:
            proof.append({"position": "left", "hash": level[idx - 1]})
        idx //= 2
        level = nxt
    return proof


def verify_proof(leaf: str, proof: list[dict], root: str) -> bool:
    computed = leaf
    for step in proof:
        computed = (_pair(computed, step["hash"]) if step["position"] == "right"
                    else _pair(step["hash"], computed))
    return computed == root


# --------------------------------------------------------------------------
# Registry operations (take a db connection + signing key; no web code)
# --------------------------------------------------------------------------

def all_leaves(db) -> list[str]:
    rows = db.execute(
        "SELECT file_hash FROM registrations ORDER BY leaf_index ASC"
    ).fetchall()
    return [r["file_hash"] for r in rows]


def registry_size(db) -> int:
    return db.execute("SELECT COUNT(*) AS c FROM registrations").fetchone()["c"]


def find_by_hash(db, file_hash: str):
    return db.execute(
        "SELECT * FROM registrations WHERE file_hash = ?", (file_hash,)
    ).fetchone()


class DuplicateRegistration(Exception):
    """Raised when a hash is already registered; carries the existing row."""

    def __init__(self, existing):
        self.existing = existing
        super().__init__("already registered")


def register(db, key: bytes, *, file_hash: str, filename: str, description: str,
             creator_id: int, creator_handle: str) -> dict:
    """Insert a new registration and return its certificate data + Merkle proof."""
    existing = find_by_hash(db, file_hash)
    if existing:
        raise DuplicateRegistration(existing)

    leaf_index = registry_size(db)  # 0-based position = current count
    registry_id = new_registry_id()
    created_at = now_iso()
    signature = sign_registration(
        key, registry_id, file_hash, filename, description or "",
        creator_handle, created_at, leaf_index,
    )

    db.execute(
        """INSERT INTO registrations
           (registry_id, creator_id, filename, file_hash, description,
            leaf_index, created_at, signature)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (registry_id, creator_id, filename, file_hash, description or None,
         leaf_index, created_at, signature),
    )
    db.commit()

    leaves = all_leaves(db)
    return {
        "registry_id": registry_id,
        "filename": filename,
        "file_hash": file_hash,
        "description": description,
        "created_at": created_at,
        "leaf_index": leaf_index,
        "registry_size": len(leaves),
        "signature": signature,
        "merkle_root": merkle_root(leaves),
        "proof": merkle_proof(leaves, leaf_index),
    }
