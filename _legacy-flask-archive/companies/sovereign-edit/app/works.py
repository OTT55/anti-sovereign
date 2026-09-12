"""
Domain operations: create a work, append a step, designate the master, and
identify a file.

No Flask here — routes call into this. That keeps the rules in one place and
makes them testable without a web server.
"""

import re

from .chain import GENESIS, block_hash, lineage_hash, step_fields, verify_chain
from .util import STEP_TYPES, new_work_id, now_iso

SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


class BadInput(Exception):
    pass


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------

def get_work(db, work_id: str):
    return db.execute("SELECT * FROM works WHERE work_id = ?", (work_id,)).fetchone()


def get_chain(db, work_id: str):
    return db.execute(
        "SELECT * FROM steps WHERE work_id = ? ORDER BY seq ASC", (work_id,)
    ).fetchall()


def list_works(db):
    return db.execute(
        """SELECT w.*, COUNT(s.id) AS step_count
           FROM works w LEFT JOIN steps s ON s.work_id = w.work_id
           GROUP BY w.work_id ORDER BY w.id DESC"""
    ).fetchall()


def master_step(db, work_id: str):
    return db.execute(
        "SELECT * FROM steps WHERE work_id = ? AND is_master = 1", (work_id,)
    ).fetchone()


# --------------------------------------------------------------------------
# Writes
# --------------------------------------------------------------------------

def append_step(db, work_id: str, *, step_type: str, actor: str, tool: str = "",
                notes: str = "", filename: str = "", file_hash: str = "") -> str:
    """Add a block to the work's chain. Returns the new block hash."""
    if step_type not in STEP_TYPES:
        raise BadInput(f"Unknown step type: {step_type}")
    if not actor.strip():
        raise BadInput("Actor / crew is required.")
    file_hash = (file_hash or "").strip().lower()
    if file_hash and not SHA256_RE.match(file_hash):
        raise BadInput("Invalid SHA-256 file hash.")

    chain = get_chain(db, work_id)
    seq = len(chain)
    prev = chain[-1]["block_hash"] if chain else GENESIS
    created_at = now_iso()

    fields = {
        "work_id": work_id, "seq": seq, "step_type": step_type,
        "actor": actor.strip(), "tool": tool.strip(), "notes": notes.strip(),
        "filename": filename.strip(), "file_hash": file_hash,
        "created_at": created_at,
    }
    bh = block_hash(prev, fields)

    db.execute(
        """INSERT INTO steps
           (work_id, seq, step_type, actor, tool, notes, filename, file_hash,
            created_at, prev_hash, block_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (work_id, seq, step_type, actor.strip(), tool.strip(), notes.strip(),
         filename.strip(), file_hash, created_at, prev, bh),
    )
    db.commit()
    return bh


def create_work(db, *, title: str, director: str) -> str:
    if not title.strip() or not director.strip():
        raise BadInput("Title and director are required.")
    work_id = new_work_id()
    db.execute(
        "INSERT INTO works (work_id, title, director, created_at) VALUES (?, ?, ?, ?)",
        (work_id, title.strip(), director.strip(), now_iso()),
    )
    db.commit()
    # Genesis block, so every work's chain starts from a recorded event.
    append_step(db, work_id, step_type="Registration", actor=director.strip(),
                tool="Sovereign Edit", notes=f"Work '{title.strip()}' registered.")
    return work_id


def set_master(db, work_id: str, seq: int) -> None:
    """Designate one step as the approved master. Only one per work."""
    row = db.execute(
        "SELECT 1 FROM steps WHERE work_id = ? AND seq = ?", (work_id, seq)
    ).fetchone()
    if not row:
        raise BadInput("No such step in this work.")
    db.execute("UPDATE steps SET is_master = 0 WHERE work_id = ?", (work_id,))
    db.execute(
        "UPDATE steps SET is_master = 1 WHERE work_id = ? AND seq = ?", (work_id, seq)
    )
    db.commit()


# --------------------------------------------------------------------------
# The core question: "which cut is this?"
# --------------------------------------------------------------------------

def identify(db, file_hash: str) -> dict:
    """Given a file's hash, say exactly what it is.

    This is the question the product exists to answer: you're holding a file and
    you need to know whether it's the approved master, an earlier stage, or not
    part of this production at all.
    """
    file_hash = (file_hash or "").strip().lower()
    if not SHA256_RE.match(file_hash):
        raise BadInput("Invalid SHA-256 file hash.")

    row = db.execute(
        "SELECT * FROM steps WHERE file_hash = ? ORDER BY id ASC LIMIT 1",
        (file_hash,),
    ).fetchone()
    if not row:
        return {"found": False, "verdict": "UNKNOWN", "file_hash": file_hash}

    work = get_work(db, row["work_id"])
    chain = get_chain(db, row["work_id"])
    intact, broken_at = verify_chain(chain)
    master = master_step(db, row["work_id"])

    if row["is_master"]:
        verdict = "APPROVED_MASTER"
    elif master:
        verdict = "NOT_THE_MASTER"
    else:
        verdict = "IN_LINEAGE"

    return {
        "found": True,
        "verdict": verdict,
        "file_hash": file_hash,
        "work_id": work["work_id"],
        "title": work["title"],
        "director": work["director"],
        "step": {
            "seq": row["seq"], "step_type": row["step_type"], "actor": row["actor"],
            "tool": row["tool"], "filename": row["filename"],
            "created_at": row["created_at"], "block_hash": row["block_hash"],
        },
        "master": None if not master else {
            "seq": master["seq"], "step_type": master["step_type"],
            "filename": master["filename"], "file_hash": master["file_hash"],
        },
        "chain_intact": intact,
        "chain_broken_at": broken_at,
        "step_count": len(chain),
        "lineage_hash": lineage_hash(chain),
    }


def work_summary(db, work_id: str) -> dict | None:
    work = get_work(db, work_id)
    if not work:
        return None
    chain = get_chain(db, work_id)
    intact, broken_at = verify_chain(chain)
    master = master_step(db, work_id)
    return {
        "work_id": work["work_id"], "title": work["title"],
        "director": work["director"], "created_at": work["created_at"],
        "step_count": len(chain), "chain_intact": intact,
        "chain_broken_at": broken_at, "lineage_hash": lineage_hash(chain),
        "master_seq": master["seq"] if master else None,
    }
