"""Phase 4 — the Memory Engine: version chains and knowledge history.

Phase 2 can tell that an incoming document is version 2 of something. This is
what makes that worth knowing: it keeps the chain, so *"what changed between
V4 and V9"* has real data behind it rather than a guess.

Two histories, and they answer different questions:

* **Document versions** — a linked chain. Answers "what did this say before?"
* **Knowledge history** — when each entity and relationship was *first seen*,
  when it was *last seen*, and whether it still holds. Answers the harder and
  more useful question: **"what did we stop believing, and when?"**

The second is the one a document store normally cannot answer at all. A fact
that quietly disappears between two drafts is invisible if you only keep the
latest version — and a fact being *removed* is often more significant than one
being added. Somebody took it out.

Append-only throughout: nothing is deleted, a fact that stops appearing is
marked closed rather than erased. Same discipline as CreativeOS's graph, and
for the same reason — the record of what was believed is itself the product.
"""

from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS document_versions (
    doc_id          TEXT PRIMARY KEY,
    previous_doc_id TEXT,
    version         INTEGER NOT NULL DEFAULT 1,
    content_hash    TEXT NOT NULL,
    similarity      REAL NOT NULL DEFAULT 0.0,
    recorded_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL,          -- "entity" | "relationship"
    signature   TEXT NOT NULL,          -- what makes this fact unique
    label       TEXT NOT NULL,          -- human-readable form
    doc_id      TEXT NOT NULL,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL,
    closed_at   TEXT,                   -- when it stopped appearing
    UNIQUE (kind, signature, doc_id)
);

CREATE INDEX IF NOT EXISTS idx_versions_previous ON document_versions(previous_doc_id);
CREATE INDEX IF NOT EXISTS idx_history_signature ON knowledge_history(signature);
CREATE INDEX IF NOT EXISTS idx_history_doc ON knowledge_history(doc_id);
"""


def _now():
    return datetime.now(timezone.utc).isoformat()


class MemoryEngine:
    """Version chains and knowledge history. Shares the store's connection."""

    def __init__(self, conn):
        self.conn = conn
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # -- document versions -------------------------------------------------

    def record_version(self, doc_id, content_hash, previous_doc_id=None, similarity=0.0):
        """Register a document, linked to the version it replaces.

        Version numbers are derived from the predecessor rather than passed in,
        so a caller cannot accidentally create two version 3s.
        """
        version = 1
        if previous_doc_id is not None:
            row = self.conn.execute(
                "SELECT version FROM document_versions WHERE doc_id = ?", (previous_doc_id,)
            ).fetchone()
            version = (row["version"] + 1) if row else 2

        self.conn.execute(
            """INSERT OR REPLACE INTO document_versions
               (doc_id, previous_doc_id, version, content_hash, similarity, recorded_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (doc_id, previous_doc_id, version, content_hash, similarity, _now()),
        )
        self.conn.commit()
        return version

    def version_of(self, doc_id):
        row = self.conn.execute(
            "SELECT version FROM document_versions WHERE doc_id = ?", (doc_id,)
        ).fetchone()
        return row["version"] if row else None

    def chain(self, doc_id):
        """Every version of a document, oldest first.

        Walked backwards from any member then reversed, so a caller holding
        *any* version can see the whole line — they rarely hold the newest.
        """
        out, current, seen = [], doc_id, set()
        while current and current not in seen:
            seen.add(current)
            row = self.conn.execute(
                "SELECT * FROM document_versions WHERE doc_id = ?", (current,)
            ).fetchone()
            if row is None:
                break
            out.append(dict(row))
            current = row["previous_doc_id"]
        return list(reversed(out))

    def latest(self, doc_id):
        """The newest version in this document's chain.

        Follows successors forward, so passing an old id still lands on the
        current one — which is what an application holding a stale reference
        needs.
        """
        current = doc_id
        seen = set()
        while current not in seen:
            seen.add(current)
            row = self.conn.execute(
                "SELECT doc_id FROM document_versions WHERE previous_doc_id = ?", (current,)
            ).fetchone()
            if row is None:
                return current
            current = row["doc_id"]
        return current

    # -- knowledge history -------------------------------------------------

    def observe(self, doc_id, facts):
        """Record the facts present in a document version.

        `facts` is `[{"kind", "signature", "label"}, ...]`.

        Anything previously seen in this document's *lineage* but absent now is
        **closed** — that is the removal detection, and it is the whole point of
        keeping this. Returns what changed.
        """
        now = _now()
        incoming = {(f["kind"], f["signature"]): f for f in facts}

        lineage = [v["doc_id"] for v in self.chain(doc_id)]
        placeholders = ",".join("?" for _ in lineage) or "''"
        previous = self.conn.execute(
            f"""SELECT kind, signature, label, id, closed_at FROM knowledge_history
                WHERE doc_id IN ({placeholders})""", lineage
        ).fetchall() if lineage else []

        known = {(r["kind"], r["signature"]): r for r in previous}
        added, retained, closed = [], [], []

        for key, fact in incoming.items():
            existing = known.get(key)
            if existing is None:
                self.conn.execute(
                    """INSERT OR IGNORE INTO knowledge_history
                       (kind, signature, label, doc_id, first_seen, last_seen)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (fact["kind"], fact["signature"], fact["label"], doc_id, now, now),
                )
                added.append(fact["label"])
            else:
                # Seen again — extend its life and reopen it if it had lapsed.
                self.conn.execute(
                    "UPDATE knowledge_history SET last_seen = ?, closed_at = NULL WHERE id = ?",
                    (now, existing["id"]),
                )
                retained.append(fact["label"])

        for key, row in known.items():
            if key not in incoming and row["closed_at"] is None:
                self.conn.execute(
                    "UPDATE knowledge_history SET closed_at = ? WHERE id = ?",
                    (now, row["id"]),
                )
                closed.append(row["label"])

        self.conn.commit()
        return {"added": added, "retained": retained, "closed": closed}

    def live_facts(self, doc_id):
        """Facts still holding across this document's lineage."""
        lineage = [v["doc_id"] for v in self.chain(doc_id)] or [doc_id]
        placeholders = ",".join("?" for _ in lineage)
        rows = self.conn.execute(
            f"""SELECT * FROM knowledge_history
                WHERE doc_id IN ({placeholders}) AND closed_at IS NULL
                ORDER BY first_seen ASC""", lineage
        ).fetchall()
        return [dict(r) for r in rows]

    def closed_facts(self, doc_id):
        """Facts that stopped appearing — what somebody took out.

        Usually the more interesting list. A fact being removed between drafts
        is a decision; a fact being added is often just detail.
        """
        lineage = [v["doc_id"] for v in self.chain(doc_id)] or [doc_id]
        placeholders = ",".join("?" for _ in lineage)
        rows = self.conn.execute(
            f"""SELECT * FROM knowledge_history
                WHERE doc_id IN ({placeholders}) AND closed_at IS NOT NULL
                ORDER BY closed_at ASC""", lineage
        ).fetchall()
        return [dict(r) for r in rows]

    def timeline(self, doc_id):
        """The document's whole life: each version, and what it changed."""
        out = []
        for entry in self.chain(doc_id):
            facts = self.conn.execute(
                """SELECT label, first_seen, closed_at FROM knowledge_history
                   WHERE doc_id = ? ORDER BY first_seen ASC""", (entry["doc_id"],)
            ).fetchall()
            out.append({
                "doc_id": entry["doc_id"],
                "version": entry["version"],
                "recorded_at": entry["recorded_at"],
                "similarity_to_previous": entry["similarity"],
                "introduced": [f["label"] for f in facts],
                "closed": [f["label"] for f in facts if f["closed_at"]],
            })
        return out

    def summary(self, doc_id):
        chain = self.chain(doc_id)
        return {
            "versions": len(chain),
            "current_version": chain[-1]["version"] if chain else None,
            "live_facts": len(self.live_facts(doc_id)),
            "closed_facts": len(self.closed_facts(doc_id)),
        }
