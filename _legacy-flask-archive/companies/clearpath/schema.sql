-- Clearpath — production database schema.
--
-- Two tables:
--   rulesets — immutable, versioned snapshots of a rule pack + the reference
--              data it was evaluated against, frozen together (decisions/0002).
--              A new version is a new row, never an edit in place, so any
--              audit entry that names a ruleset_id resolves forever to
--              exactly the rules that were live when it decided.
--   audit    — every routing decision, hash-chained (same mechanism as the
--              MVP) and now pinned to the ruleset that produced it.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS rulesets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    pack          TEXT    NOT NULL,
    version       TEXT    NOT NULL,
    content_hash  TEXT    NOT NULL,          -- SHA-256 over the frozen rules+refdata JSON
    loaded_at     TEXT    NOT NULL,
    rules_json    TEXT    NOT NULL,          -- verbatim frozen rule definitions
    refdata_json  TEXT    NOT NULL,          -- verbatim frozen reference data
    UNIQUE(pack, version)
);

CREATE TABLE IF NOT EXISTS audit (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id     TEXT    NOT NULL UNIQUE,
    created_at  TEXT    NOT NULL,
    ruleset_id  INTEGER NOT NULL REFERENCES rulesets(id),
    payload     TEXT    NOT NULL,            -- {"facts":..., "decision":..., "findings":[...]}
    prev_hash   TEXT    NOT NULL,
    entry_hash  TEXT    NOT NULL             -- SHA-256(prev_hash + canonical(payload))
);

CREATE INDEX IF NOT EXISTS idx_audit_case ON audit(case_id);
