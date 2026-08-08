-- Sovereign Edit — production database schema.
--
-- Written for SQLite today; kept to the subset of SQL that ports cleanly to
-- PostgreSQL later. Two tables:
--   works — a film/edit being tracked
--   steps — the hash-linked production lineage; each row commits to the one
--           before it, so altering history is detectable

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS works (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id    TEXT    NOT NULL UNIQUE,   -- public id, e.g. "SE-AB12CD34EF"
    title      TEXT    NOT NULL,
    director   TEXT    NOT NULL,
    created_at TEXT    NOT NULL           -- UTC ISO-8601
);

-- One row per production step = one block in the work's chain.
CREATE TABLE IF NOT EXISTS steps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id     TEXT    NOT NULL REFERENCES works(work_id),
    seq         INTEGER NOT NULL,          -- 0-based position in the chain
    step_type   TEXT    NOT NULL,          -- Capture, Edit, Colour Grade, ...
    actor       TEXT    NOT NULL,          -- who did it
    tool        TEXT,                      -- what they used
    notes       TEXT,
    filename    TEXT,                      -- the artefact's name at this stage
    file_hash   TEXT,                      -- SHA-256 of the artefact (hashed in-browser)
    created_at  TEXT    NOT NULL,

    -- The chain: block_hash = SHA-256(prev_hash + canonical(step fields)).
    prev_hash   TEXT    NOT NULL,
    block_hash  TEXT    NOT NULL,

    -- Which cut is the approved master. Deliberately OUTSIDE the block hash:
    -- the chain records what happened (immutable); the master designation is a
    -- decision you're allowed to change. See decisions/0002.
    is_master   INTEGER NOT NULL DEFAULT 0,

    UNIQUE (work_id, seq)
);

-- Look-ups we actually make: identify a file by hash, walk a work's chain.
CREATE INDEX IF NOT EXISTS idx_steps_hash ON steps(file_hash);
CREATE INDEX IF NOT EXISTS idx_steps_work ON steps(work_id, seq);
