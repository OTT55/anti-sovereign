"""The Storage Engine — *"Files. Media. Metadata. Versions. Snapshots."*

The graph holds knowledge; this holds the artefacts that knowledge came from —
a manuscript, a cut, a contract PDF. Two decisions shape it:

**Content addressing.** A file is identified by the SHA-256 of its bytes, not by
its name or a serial number. The same bytes stored twice are one blob, and a
file that changes gets a genuinely new identity rather than silently replacing
the old one. Provenance depends on that: "the fact came from *this* draft" is
meaningless if the draft can change underneath the claim.

**Versions are a chain, not an overwrite.** Storing a new revision links it to
its predecessor, so history is walkable — the same append-only discipline the
graph uses, applied to bytes.

Blobs are stored as bytes in SQLite. That is right at this scale and wrong at
video scale; the interface is deliberately narrow so a filesystem or object
store can replace the body without callers noticing.
"""

import hashlib

from ..graph import ids

SCHEMA = """
CREATE TABLE IF NOT EXISTS blobs (
    digest      TEXT PRIMARY KEY,
    size        INTEGER NOT NULL,
    content     BLOB NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
    id           TEXT PRIMARY KEY,
    space_id  TEXT NOT NULL,
    name         TEXT NOT NULL,
    digest       TEXT NOT NULL REFERENCES blobs(digest),
    media_type   TEXT NOT NULL DEFAULT 'application/octet-stream',
    entity_id    TEXT,
    previous_id  TEXT,
    version      INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_files_space ON files(space_id, name);
CREATE INDEX IF NOT EXISTS idx_files_entity ON files(entity_id);
CREATE INDEX IF NOT EXISTS idx_files_digest ON files(digest);
"""

FILE = "FIL"


class StoredFile:
    __slots__ = ("id", "space_id", "name", "digest", "media_type",
                 "entity_id", "previous_id", "version", "created_at")

    def __init__(self, id, space_id, name, digest, media_type, entity_id,
                 previous_id, version, created_at):
        self.id = id
        self.space_id = space_id
        self.name = name
        self.digest = digest
        self.media_type = media_type
        self.entity_id = entity_id
        self.previous_id = previous_id
        self.version = version
        self.created_at = created_at

    def describe(self):
        return f"{self.name} v{self.version} ({self.digest[:12]}…)"

    def __repr__(self):
        return f"<StoredFile {self.describe()}>"


def digest_of(content):
    return hashlib.sha256(content).hexdigest()


class StorageEngine:
    """Content-addressed blobs plus a version chain per logical file."""

    def __init__(self, conn):
        self.conn = conn
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def put(self, space_id, name, content, media_type="application/octet-stream",
            entity_id=None, replaces=None):
        """Store bytes and register them as a file.

        `replaces` links this to a previous version, making the chain walkable.
        Identical bytes stored twice share one blob but still get their own file
        record, because the same content can legitimately appear under two names.
        """
        if isinstance(content, str):
            content = content.encode("utf-8")
        digest = digest_of(content)
        now = ids.now()

        self.conn.execute(
            "INSERT OR IGNORE INTO blobs (digest, size, content, created_at) VALUES (?, ?, ?, ?)",
            (digest, len(content), content, now),
        )

        version = 1
        if replaces is not None:
            previous = self.get(replaces)
            if previous is None:
                raise ValueError(f"No such file to replace: {replaces}")
            version = previous.version + 1

        file_id = ids.new_id(FILE)
        self.conn.execute(
            """INSERT INTO files (id, space_id, name, digest, media_type,
                                  entity_id, previous_id, version, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (file_id, space_id, name, digest, media_type, entity_id,
             replaces, version, now),
        )
        self.conn.commit()
        return StoredFile(file_id, space_id, name, digest, media_type,
                          entity_id, replaces, version, now)

    def get(self, file_id):
        row = self.conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
        return _to_file(row) if row else None

    def read(self, file_id):
        """The bytes of a file, or `None` if it does not exist."""
        row = self.conn.execute(
            "SELECT b.content FROM files f JOIN blobs b ON b.digest = f.digest "
            "WHERE f.id = ?", (file_id,)
        ).fetchone()
        return row["content"] if row else None

    def read_text(self, file_id, encoding="utf-8"):
        content = self.read(file_id)
        return content.decode(encoding) if content is not None else None

    def history(self, file_id):
        """Every version of a file, oldest first — the chain walked backwards
        then reversed, so a caller holding any version can see the whole line."""
        chain, current = [], self.get(file_id)
        while current is not None:
            chain.append(current)
            current = self.get(current.previous_id) if current.previous_id else None
        return list(reversed(chain))

    def latest(self, space_id, name):
        """The newest version of a named file."""
        row = self.conn.execute(
            "SELECT * FROM files WHERE space_id = ? AND name = ? "
            "ORDER BY version DESC, created_at DESC LIMIT 1",
            (space_id, name),
        ).fetchone()
        return _to_file(row) if row else None

    def for_entity(self, entity_id):
        rows = self.conn.execute(
            "SELECT * FROM files WHERE entity_id = ? ORDER BY created_at ASC",
            (entity_id,),
        ).fetchall()
        return [_to_file(r) for r in rows]

    def duplicates(self, space_id):
        """Files whose bytes are identical — the same asset stored twice under
        different names, which is worth knowing before it multiplies."""
        rows = self.conn.execute(
            """SELECT digest, COUNT(*) n FROM files WHERE space_id = ?
               GROUP BY digest HAVING n > 1""",
            (space_id,),
        ).fetchall()
        out = {}
        for row in rows:
            files = self.conn.execute(
                "SELECT * FROM files WHERE space_id = ? AND digest = ?",
                (space_id, row["digest"]),
            ).fetchall()
            out[row["digest"]] = [_to_file(f) for f in files]
        return out

    def stats(self, space_id):
        row = self.conn.execute(
            """SELECT COUNT(*) files, COUNT(DISTINCT f.digest) blobs,
                      COALESCE(SUM(b.size), 0) stored
               FROM files f JOIN blobs b ON b.digest = f.digest
               WHERE f.space_id = ?""",
            (space_id,),
        ).fetchone()
        return {"files": row["files"], "blobs": row["blobs"], "bytes": row["stored"]}


def _to_file(row):
    return StoredFile(
        id=row["id"], space_id=row["space_id"], name=row["name"],
        digest=row["digest"], media_type=row["media_type"],
        entity_id=row["entity_id"], previous_id=row["previous_id"],
        version=row["version"], created_at=row["created_at"],
    )
