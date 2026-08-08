"""The durable, append-only event log.

Events are written here **before** any subscriber is told about them. If the
process dies mid-dispatch the event is still on disk, and whoever missed it
catches up by replaying from their cursor. A bus that only held events in memory
would lose exactly the events that matter most — the ones in flight when
something broke.

Shares the SQLite connection with the graph store on purpose: a graph write and
the event announcing it land in the same database, so they cannot disagree about
what happened.
"""

from .. graph import ids
from .model import Event, from_json, to_json

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    sequence    INTEGER PRIMARY KEY AUTOINCREMENT,
    id          TEXT NOT NULL UNIQUE,
    space_id TEXT NOT NULL,
    kind        TEXT NOT NULL,
    subject_id  TEXT NOT NULL DEFAULT '',
    payload     TEXT NOT NULL DEFAULT '{}',
    occurred_at TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT 'creativeos'
);

CREATE INDEX IF NOT EXISTS idx_events_space ON events(space_id, sequence);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind, sequence);
CREATE INDEX IF NOT EXISTS idx_events_subject ON events(subject_id, sequence);
"""

EVENT = "EVT"


def _to_event(row):
    return Event(
        id=row["id"], sequence=row["sequence"], space_id=row["space_id"],
        kind=row["kind"], subject_id=row["subject_id"],
        payload=from_json(row["payload"]), occurred_at=row["occurred_at"],
        source=row["source"],
    )


class EventLog:
    """Append-only storage for events. Never updates, never deletes."""

    def __init__(self, conn):
        self.conn = conn
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def append(self, space_id, kind, subject_id="", payload=None, source="creativeos"):
        """Record that something happened. Returns the stored `Event`, including
        the sequence number SQLite assigned it."""
        event_id = ids.new_id(EVENT)
        occurred_at = ids.now()
        cur = self.conn.execute(
            """INSERT INTO events (id, space_id, kind, subject_id, payload, occurred_at, source)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (event_id, space_id, kind, subject_id, to_json(payload or {}), occurred_at, source),
        )
        self.conn.commit()
        return Event(
            id=event_id, sequence=cur.lastrowid, space_id=space_id, kind=kind,
            subject_id=subject_id, payload=dict(payload or {}), occurred_at=occurred_at,
            source=source,
        )

    def since(self, sequence=0, space_id=None, kind=None, limit=None):
        """Every event after `sequence`, oldest first — the replay primitive.

        A subscriber that was offline (or that did not exist when the events
        happened) stores the last sequence it handled and calls this to catch
        up. That is what makes the ecosystem reactive rather than merely
        decoupled.
        """
        sql = "SELECT * FROM events WHERE sequence > ?"
        params = [sequence]
        if space_id is not None:
            sql += " AND space_id = ?"
            params.append(space_id)
        if kind is not None:
            if kind.endswith(".*"):
                sql += " AND kind LIKE ?"
                params.append(kind[:-1] + "%")
            elif kind != "*":
                sql += " AND kind = ?"
                params.append(kind)
        sql += " ORDER BY sequence ASC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        return [_to_event(r) for r in self.conn.execute(sql, params).fetchall()]

    def about(self, subject_id):
        """Everything that ever happened to one entity, oldest first."""
        rows = self.conn.execute(
            "SELECT * FROM events WHERE subject_id = ? ORDER BY sequence ASC", (subject_id,)
        ).fetchall()
        return [_to_event(r) for r in rows]

    def latest_sequence(self):
        row = self.conn.execute("SELECT MAX(sequence) s FROM events").fetchone()
        return row["s"] or 0

    def count(self):
        return self.conn.execute("SELECT COUNT(*) c FROM events").fetchone()["c"]
