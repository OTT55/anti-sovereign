"""SQLite persistence — plain sqlite3, no web framework request-context coupling.
A Store is a connection you open, use, and close; safe to point at a file or ":memory:".
"""

import sqlite3
from pathlib import Path


class Store:
    def __init__(self, path=":memory:"):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS documents (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id     TEXT NOT NULL UNIQUE,
                title      TEXT NOT NULL,
                category   TEXT NOT NULL DEFAULT 'general',
                created_at TEXT NOT NULL
            )"""
        )
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS chunks (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id TEXT NOT NULL,
                seq    INTEGER NOT NULL,
                text   TEXT NOT NULL
            )"""
        )
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS entities (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id TEXT NOT NULL,
                name   TEXT NOT NULL,
                type   TEXT NOT NULL
            )"""
        )
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS relationships (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id    TEXT NOT NULL,
                source_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                label     TEXT NOT NULL
            )"""
        )
        self.conn.commit()

    def add_document(self, doc_id, title, category, created_at):
        self.conn.execute(
            "INSERT INTO documents (doc_id, title, category, created_at) VALUES (?, ?, ?, ?)",
            (doc_id, title, category, created_at),
        )

    def add_chunks(self, doc_id, chunks):
        self.conn.executemany(
            "INSERT INTO chunks (doc_id, seq, text) VALUES (?, ?, ?)",
            [(doc_id, i, c) for i, c in enumerate(chunks)],
        )

    def add_entities_relationships(self, doc_id, entities, relationships):
        """entities: [{"name", "type"}]  relationships: [{"source", "target", "label"}]
        (matching names to the row ids just inserted). Returns (entity_count, relationship_count).
        """
        name_to_id = {}
        for e in entities:
            cur = self.conn.execute(
                "INSERT INTO entities (doc_id, name, type) VALUES (?, ?, ?)",
                (doc_id, e["name"], e["type"]),
            )
            name_to_id[e["name"]] = cur.lastrowid

        rel_count = 0
        for r in relationships:
            src_id, tgt_id = name_to_id.get(r["source"]), name_to_id.get(r["target"])
            if src_id is None or tgt_id is None:
                continue
            self.conn.execute(
                "INSERT INTO relationships (doc_id, source_id, target_id, label) VALUES (?, ?, ?, ?)",
                (doc_id, src_id, tgt_id, r["label"]),
            )
            rel_count += 1
        return len(name_to_id), rel_count

    def commit(self):
        self.conn.commit()

    def get_document(self, doc_id):
        row = self.conn.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None

    def list_documents(self, category="general"):
        rows = self.conn.execute(
            """SELECT d.doc_id, d.title, d.created_at, COUNT(c.id) chunk_count
               FROM documents d LEFT JOIN chunks c ON c.doc_id = d.doc_id
               WHERE d.category = ?
               GROUP BY d.doc_id ORDER BY d.id DESC""",
            (category,),
        ).fetchall()
        return [dict(r) for r in rows]

    def load_chunks(self, doc_id):
        rows = self.conn.execute(
            "SELECT text FROM chunks WHERE doc_id = ? ORDER BY seq ASC", (doc_id,)
        ).fetchall()
        return [r["text"] for r in rows]

    def load_collection_chunks(self, category):
        """Pool chunks across every document in a category, tagged with their source doc."""
        rows = self.conn.execute(
            """SELECT c.text, c.seq, d.doc_id, d.title
               FROM chunks c JOIN documents d ON d.doc_id = c.doc_id
               WHERE d.category = ?
               ORDER BY d.id ASC, c.seq ASC""",
            (category,),
        ).fetchall()
        return [{"text": r["text"], "doc_id": r["doc_id"], "title": r["title"]} for r in rows]

    def entity_count(self, doc_ids):
        placeholders = ",".join("?" for _ in doc_ids)
        row = self.conn.execute(
            f"SELECT COUNT(*) c FROM entities WHERE doc_id IN ({placeholders})", doc_ids
        ).fetchone()
        return row["c"]

    def load_graph_data(self, doc_ids):
        """Returns (entities, relationships) as plain dicts for graph.build_graph()."""
        placeholders = ",".join("?" for _ in doc_ids)
        ent_rows = self.conn.execute(
            f"SELECT id, doc_id, name, type FROM entities WHERE doc_id IN ({placeholders})", doc_ids
        ).fetchall()
        rel_rows = self.conn.execute(
            f"SELECT source_id, target_id, label FROM relationships WHERE doc_id IN ({placeholders})", doc_ids
        ).fetchall()

        id_to_name_type = {r["id"]: (r["name"], r["type"]) for r in ent_rows}
        entities_by_key = {}
        for r in ent_rows:
            key = (r["name"], r["type"])
            if key not in entities_by_key:
                entities_by_key[key] = {"name": r["name"], "type": r["type"], "doc_ids": set()}
            entities_by_key[key]["doc_ids"].add(r["doc_id"])

        relationships = []
        for r in rel_rows:
            src = id_to_name_type.get(r["source_id"])
            tgt = id_to_name_type.get(r["target_id"])
            if src is None or tgt is None:
                continue
            relationships.append({"source": src[0], "target": tgt[0], "label": r["label"]})

        return list(entities_by_key.values()), relationships

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
