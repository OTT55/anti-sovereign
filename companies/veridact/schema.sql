-- Veridact — production database schema.
--
-- Written for SQLite today; kept to the subset of SQL that ports cleanly to
-- PostgreSQL later. Two tables:
--   devices   — enrolled capture devices/creators, identified by their PUBLIC key.
--               Veridact stores only public keys, so it can verify signatures but
--               never forge one (decisions/0002).
--   manifests — signed capture records. Each is a device's cryptographic statement
--               "I captured media with this hash at this time," plus the signature.

PRAGMA foreign_keys = ON;

-- An enrolled capture device / creator. The private key never reaches us.
--
-- `algorithm` picks which verifier checks this device's signatures (decisions/0004):
--   'schnorr'     — custom Fiat-Shamir Schnorr over RFC3526 group 14 (crypto.py)
--   'ecdsa-p256'  — NIST P-256 via Web Crypto + the `cryptography` library
--                   (crypto_ecdsa.py) — the peer-reviewed, universally-supported
--                   option; the default for new enrolments going forward.
-- `public_key`'s encoding depends on `algorithm`: a decimal integer for Schnorr,
-- a hex-encoded raw EC point (0x04 || X || Y) for ecdsa-p256.
CREATE TABLE IF NOT EXISTS devices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    handle      TEXT    NOT NULL UNIQUE,        -- human label, e.g. "ott-pixel-8"
    public_key  TEXT    NOT NULL,
    algorithm   TEXT    NOT NULL DEFAULT 'schnorr',
    created_at  TEXT    NOT NULL                -- UTC ISO-8601
);

-- One-time freshness challenges. Veridact issues one before a capture; the
-- browser must include it in the signed message and can use it only once, within
-- a short window. This is what makes a signature provably *live* rather than
-- pre-computed or replayed (decisions/0003).
CREATE TABLE IF NOT EXISTS capture_challenges (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nonce      TEXT    NOT NULL UNIQUE,         -- random hex issued to the browser
    issued_at  TEXT    NOT NULL,                -- UTC ISO-8601
    used_at    TEXT                             -- set when consumed; NULL = unused
);

-- A signed capture manifest: the provenance record that travels with a file.
--
-- `sig_algorithm` mirrors the signing device's `algorithm`, read at attest time
-- so a manifest remains verifiable even if a device's default algorithm choice
-- changes later. Signature encoding, by algorithm:
--   'schnorr'     — sig_t, sig_s are the two Schnorr components, decimal strings.
--   'ecdsa-p256'  — sig_t holds the full raw r||s signature as hex (exactly what
--                   Web Crypto's subtle.sign() returns); sig_s is unused ('').
CREATE TABLE IF NOT EXISTS manifests (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    manifest_id   TEXT    NOT NULL UNIQUE,       -- public id, e.g. "VD-AB12CD34EF56"
    device_id     INTEGER NOT NULL REFERENCES devices(id),
    media_hash    TEXT    NOT NULL,              -- SHA-256 of the captured media
    label         TEXT    NOT NULL,              -- what it is, e.g. "street interview"
    challenge     TEXT    NOT NULL,              -- the freshness nonce, part of the signature
    captured_at   TEXT    NOT NULL,              -- device-asserted capture time (signed)
    received_at   TEXT    NOT NULL,              -- when Veridact received it (server clock)
    sig_algorithm TEXT    NOT NULL DEFAULT 'schnorr',
    sig_t         TEXT    NOT NULL,
    sig_s         TEXT    NOT NULL DEFAULT '',
    -- decisions/0009: a random 56-bit (7-byte, 14 hex char) secret embedded as a
    -- TrustMark soft-binding watermark BEFORE this manifest's hash was signed —
    -- so media_hash above already reflects the watermarked bytes. NULL for any
    -- manifest that predates this column. Never derived from manifest_id (public,
    -- low-entropy) — always a fresh random value, looked up by exact match only.
    watermark_secret TEXT
);

-- Verify looks a manifest up by the media hash; a device's manifests by device.
-- (idx_manifest_watermark is created in db.py's init_db, AFTER the
-- watermark_secret migration runs, so it doesn't fail on a database that
-- predates that column — see decisions/0009.)
CREATE INDEX IF NOT EXISTS idx_manifest_hash   ON manifests(media_hash);
CREATE INDEX IF NOT EXISTS idx_manifest_device ON manifests(device_id);
