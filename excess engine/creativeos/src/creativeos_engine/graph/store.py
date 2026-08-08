"""SQLite persistence for the Creative Knowledge Graph.

Plain `sqlite3` — no ORM, no web framework, no request-context coupling. The
store's only job is durable rows in and typed model objects out; every query
that means something lives in `graph.py`, so the storage layer can be swapped
later (Postgres when spaces get large, per the same scale-triggered
reasoning ContextCore documented) without touching engine code.

**Record time is stored as UTC ISO-8601 strings** and compared
lexicographically. That is only correct because every timestamp is written by
`ids.now()` at a fixed UTC offset — same format, same zone, so string order
equals chronological order. Any code writing timestamps another way would
silently break `as_of` queries.
"""

import sqlite3

from .model import Assertion, AssertionKind, Entity, Space, ValidWindow

SCHEMA = """
CREATE TABLE IF NOT EXISTS spaces (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    domain     TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entity_types (
    space_id TEXT NOT NULL REFERENCES spaces(id),
    type_name   TEXT NOT NULL,
    PRIMARY KEY (space_id, type_name)
);

CREATE TABLE IF NOT EXISTS entities (
    id          TEXT PRIMARY KEY,
    space_id TEXT NOT NULL REFERENCES spaces(id),
    kind        TEXT NOT NULL,
    subkind     TEXT NOT NULL DEFAULT '',
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assertions (
    id                TEXT PRIMARY KEY,
    space_id       TEXT NOT NULL REFERENCES spaces(id),
    kind              TEXT NOT NULL,
    subject_id        TEXT NOT NULL REFERENCES entities(id),
    predicate         TEXT NOT NULL,
    object_value      TEXT,
    object_id         TEXT REFERENCES entities(id),
    valid_start       INTEGER,
    valid_end         INTEGER,
    recorded_at       TEXT NOT NULL,
    retracted_at      TEXT,
    retraction_reason TEXT NOT NULL DEFAULT '',
    source_kind       TEXT NOT NULL DEFAULT 'authored',
    source_ref        TEXT NOT NULL DEFAULT '',
    confidence        REAL NOT NULL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS functional_predicates (
    space_id TEXT NOT NULL REFERENCES spaces(id),
    predicate   TEXT NOT NULL,
    PRIMARY KEY (space_id, predicate)
);

CREATE INDEX IF NOT EXISTS idx_entities_space ON entities(space_id, kind);
CREATE INDEX IF NOT EXISTS idx_assertions_subject ON assertions(subject_id, predicate);
CREATE INDEX IF NOT EXISTS idx_assertions_object ON assertions(object_id);
CREATE INDEX IF NOT EXISTS idx_assertions_space ON assertions(space_id, kind);
"""


def _to_entity(row):
    return Entity(
        id=row["id"], space_id=row["space_id"], kind=row["kind"],
        subkind=row["subkind"], name=row["name"], created_at=row["created_at"],
    )


def _to_assertion(row):
    return Assertion(
        id=row["id"], space_id=row["space_id"], kind=AssertionKind(row["kind"]),
        subject_id=row["subject_id"], predicate=row["predicate"],
        object_value=row["object_value"], object_id=row["object_id"],
        valid=ValidWindow(row["valid_start"], row["valid_end"]),
        recorded_at=row["recorded_at"], retracted_at=row["retracted_at"],
        retraction_reason=row["retraction_reason"], source_kind=row["source_kind"],
        source_ref=row["source_ref"], confidence=row["confidence"],
    )


class GraphStore:
    def __init__(self, path=":memory:"):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # -- writes ------------------------------------------------------------

    def add_space(self, space):
        self.conn.execute(
            "INSERT INTO spaces (id, name, domain, created_at) VALUES (?, ?, ?, ?)",
            (space.id, space.name, space.domain, space.created_at),
        )
        self.conn.commit()

    def declare_entity_type(self, space_id, type_name):
        self.conn.execute(
            "INSERT OR IGNORE INTO entity_types (space_id, type_name) VALUES (?, ?)",
            (space_id, type_name),
        )
        self.conn.commit()

    def entity_types(self, space_id):
        rows = self.conn.execute(
            "SELECT type_name FROM entity_types WHERE space_id = ?", (space_id,)
        ).fetchall()
        return {r["type_name"] for r in rows}

    def add_entity(self, entity):
        self.conn.execute(
            """INSERT INTO entities (id, space_id, kind, subkind, name, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (entity.id, entity.space_id, entity.kind, entity.subkind,
             entity.name, entity.created_at),
        )
        self.conn.commit()

    def rename_entity(self, entity_id, new_name):
        """Changes the label only. The id is immutable by design — every
        assertion referencing this entity keeps pointing at it."""
        self.conn.execute("UPDATE entities SET name = ? WHERE id = ?", (new_name, entity_id))
        self.conn.commit()

    def add_assertion(self, a):
        self.conn.execute(
            """INSERT INTO assertions
               (id, space_id, kind, subject_id, predicate, object_value, object_id,
                valid_start, valid_end, recorded_at, retracted_at, retraction_reason,
                source_kind, source_ref, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (a.id, a.space_id, a.kind.value, a.subject_id, a.predicate,
             a.object_value, a.object_id, a.valid.start, a.valid.end,
             a.recorded_at, a.retracted_at, a.retraction_reason,
             a.source_kind, a.source_ref, a.confidence),
        )
        self.conn.commit()

    def retract_assertion(self, assertion_id, retracted_at, reason):
        """The only UPDATE in the store. Everything else is append-only —
        retraction closes a fact's record-time validity, it does not erase it."""
        cur = self.conn.execute(
            "UPDATE assertions SET retracted_at = ?, retraction_reason = ? "
            "WHERE id = ? AND retracted_at IS NULL",
            (retracted_at, reason, assertion_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def declare_functional(self, space_id, predicate):
        self.conn.execute(
            "INSERT OR IGNORE INTO functional_predicates (space_id, predicate) VALUES (?, ?)",
            (space_id, predicate),
        )
        self.conn.commit()

    def undeclare_functional(self, space_id, predicate):
        self.conn.execute(
            "DELETE FROM functional_predicates WHERE space_id = ? AND predicate = ?",
            (space_id, predicate),
        )
        self.conn.commit()

    # -- reads -------------------------------------------------------------

    def functional_predicates(self, space_id):
        rows = self.conn.execute(
            "SELECT predicate FROM functional_predicates WHERE space_id = ?", (space_id,)
        ).fetchall()
        return {r["predicate"] for r in rows}

    def get_space(self, space_id):
        row = self.conn.execute("SELECT * FROM spaces WHERE id = ?", (space_id,)).fetchone()
        if row is None:
            return None
        return Space(id=row["id"], name=row["name"], domain=row["domain"],
                        created_at=row["created_at"])

    def get_entity(self, entity_id):
        row = self.conn.execute("SELECT * FROM entities WHERE id = ?", (entity_id,)).fetchone()
        return _to_entity(row) if row else None

    def find_entities(self, space_id, kind=None, name=None):
        sql = "SELECT * FROM entities WHERE space_id = ?"
        params = [space_id]
        if kind is not None:
            sql += " AND kind = ?"
            params.append(kind)
        if name is not None:
            sql += " AND name = ?"
            params.append(name)
        sql += " ORDER BY created_at ASC, id ASC"
        return [_to_entity(r) for r in self.conn.execute(sql, params).fetchall()]

    def get_assertion(self, assertion_id):
        row = self.conn.execute("SELECT * FROM assertions WHERE id = ?", (assertion_id,)).fetchone()
        return _to_assertion(row) if row else None

    def assertions_about(self, subject_id, kind=None):
        """Every assertion ever made with this entity as subject, retracted
        included — ordered oldest first, so this doubles as the entity's history."""
        sql = "SELECT * FROM assertions WHERE subject_id = ?"
        params = [subject_id]
        if kind is not None:
            sql += " AND kind = ?"
            params.append(kind.value)
        sql += " ORDER BY recorded_at ASC, id ASC"
        return [_to_assertion(r) for r in self.conn.execute(sql, params).fetchall()]

    def assertions_targeting(self, object_id):
        """Relationships pointing *at* this entity — the inbound half of
        "how is it connected?"."""
        rows = self.conn.execute(
            "SELECT * FROM assertions WHERE object_id = ? ORDER BY recorded_at ASC, id ASC",
            (object_id,),
        ).fetchall()
        return [_to_assertion(r) for r in rows]

    def assertions_in_space(self, space_id, kind=None):
        sql = "SELECT * FROM assertions WHERE space_id = ?"
        params = [space_id]
        if kind is not None:
            sql += " AND kind = ?"
            params.append(kind.value)
        sql += " ORDER BY recorded_at ASC, id ASC"
        return [_to_assertion(r) for r in self.conn.execute(sql, params).fetchall()]

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
