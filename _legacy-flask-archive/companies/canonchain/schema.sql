-- Canonchain — production database schema.
--
-- Written for SQLite today; deliberately kept to the subset of SQL that ports
-- cleanly to PostgreSQL later (see decisions/0002-database-and-data-model.md).
--
-- Three tables, one job each:
--   creators           — who can register works (multi-user-ready from day one)
--   registrations      — the registered works; each is a Merkle leaf, and each
--                        carries a tamper-evident signature (the "wax seal")
--   merkle_checkpoints — periodic signed snapshots of the tree root, so proofs
--                        scale and every root is anchored in time

PRAGMA foreign_keys = ON;

-- Who registers works. V1 seeds a single creator; the shape is already
-- multi-user so real sign-in is a later swap, not a schema change.
CREATE TABLE IF NOT EXISTS creators (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    handle       TEXT    NOT NULL UNIQUE,          -- public @handle, e.g. "ott"
    display_name TEXT    NOT NULL,
    created_at   TEXT    NOT NULL                  -- UTC ISO-8601
);

-- The registry itself. One row = one registered work = one Merkle leaf.
CREATE TABLE IF NOT EXISTS registrations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT, -- internal row id
    registry_id TEXT    NOT NULL UNIQUE,           -- public id, e.g. "CC-AB12CD34EF56"
    creator_id  INTEGER NOT NULL REFERENCES creators(id),
    filename    TEXT    NOT NULL,
    file_hash   TEXT    NOT NULL UNIQUE,           -- SHA-256 hex; the leaf value
    description TEXT,
    leaf_index  INTEGER NOT NULL UNIQUE,           -- 0-based position in the Merkle tree
    created_at  TEXT    NOT NULL,                  -- UTC ISO-8601
    signature   TEXT    NOT NULL                   -- HMAC-SHA256 over the record
);

-- Look-ups we actually make: by hash (verify), by creator (a creator's registry),
-- and by leaf position (building Merkle proofs in order).
CREATE INDEX IF NOT EXISTS idx_reg_hash    ON registrations(file_hash);
CREATE INDEX IF NOT EXISTS idx_reg_creator ON registrations(creator_id);
CREATE INDEX IF NOT EXISTS idx_reg_leaf    ON registrations(leaf_index);

-- Signed snapshots of the whole registry's Merkle root at a given size.
-- These let verification recompute proofs from a known anchor instead of from
-- scratch, and give us a timestamped, signed history of the registry's state.
CREATE TABLE IF NOT EXISTS merkle_checkpoints (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    leaf_count  INTEGER NOT NULL,                  -- tree size when snapshotted
    merkle_root TEXT    NOT NULL,                  -- root hash at that size
    created_at  TEXT    NOT NULL,
    signature   TEXT    NOT NULL                   -- HMAC over (leaf_count, root)
);
