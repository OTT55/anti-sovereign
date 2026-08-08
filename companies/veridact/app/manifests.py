"""
Veridact domain logic: enrol devices, accept signed capture manifests, and
verify media into one of three honest verdicts.

No web code here, so it can be tested on its own (Phase 3).
"""

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from . import crypto_ecdsa, watermark
from .crypto import P, manifest_message
from .crypto import verify_signature as _verify_schnorr
from .util import new_manifest_id, now_iso

SHA256_RE = re.compile(r"^[a-f0-9]{64}$")

# Algorithms a device can enrol under (decisions/0004). ECDSA P-256 is the
# peer-reviewed, universally-supported default for new enrolments; Schnorr
# remains fully supported for anything enrolled before this option existed.
ALGORITHMS = {"schnorr", "ecdsa-p256"}
DEFAULT_ALGORITHM = "ecdsa-p256"

# How long a capture challenge stays valid. Short, because its whole job is to
# prove the capture happened *now*.
CHALLENGE_TTL_SECONDS = 120


class BadInput(Exception):
    pass


class DuplicateHandle(Exception):
    pass


class InvalidSignature(Exception):
    pass


# --------------------------------------------------------------------------
# Devices
# --------------------------------------------------------------------------

def enrol_device(db, handle: str, public_key: str, algorithm: str = DEFAULT_ALGORITHM) -> str:
    handle = (handle or "").strip()
    algorithm = (algorithm or DEFAULT_ALGORITHM).strip()
    if not handle:
        raise BadInput("A device handle is required.")
    if algorithm not in ALGORITHMS:
        raise BadInput(f"Unknown algorithm: {algorithm}")

    if algorithm == "schnorr":
        try:
            y = int(public_key)
        except (TypeError, ValueError):
            raise BadInput("Malformed public key.")
        if not (1 < y < P):
            raise BadInput("Public key out of range.")
        stored_key = str(y)
    else:  # ecdsa-p256
        try:
            crypto_ecdsa.load_public_key(public_key)
        except (ValueError, TypeError):
            raise BadInput("Malformed public key.")
        stored_key = public_key.strip().lower()

    if db.execute("SELECT 1 FROM devices WHERE handle = ?", (handle,)).fetchone():
        raise DuplicateHandle("That device handle is already enrolled.")

    db.execute(
        "INSERT INTO devices (handle, public_key, algorithm, created_at) VALUES (?, ?, ?, ?)",
        (handle, stored_key, algorithm, now_iso()),
    )
    db.commit()
    return handle


def get_device(db, handle: str):
    return db.execute("SELECT * FROM devices WHERE handle = ?", (handle,)).fetchone()


# --------------------------------------------------------------------------
# Freshness challenges — proof the capture happened *now* (decisions/0003)
# --------------------------------------------------------------------------

def issue_challenge(db) -> dict:
    """Hand the capture agent a one-time nonce to fold into its signature,
    plus a manifest id reserved for this capture (decisions/0011).

    The id has to exist before the file is finished being assembled, not
    after: it gets embedded (as the PNG proof-code chunk, decisions/0008)
    before the C2PA manifest is signed (decisions/0010), because C2PA's own
    hash-binding covers the file's bytes at signing time — anything added
    afterward, including that chunk, invalidates it. Reserving the id here
    is just generating a random label ahead of time; it's never written to
    the manifests table unless a real signed `/attest` call actually uses
    it, so an abandoned capture just leaves an id that's never referenced
    anywhere, not a gap or a security concern.
    """
    nonce = secrets.token_hex(16)
    db.execute(
        "INSERT INTO capture_challenges (nonce, issued_at) VALUES (?, ?)",
        (nonce, now_iso()),
    )
    db.commit()
    return {
        "challenge": nonce, "expires_in": CHALLENGE_TTL_SECONDS,
        "manifest_id": new_manifest_id(),
    }


def _consume_challenge(db, nonce: str) -> None:
    """Validate and burn a challenge. Raises BadInput if unusable."""
    row = db.execute(
        "SELECT * FROM capture_challenges WHERE nonce = ?", (nonce,)
    ).fetchone()
    if not row:
        raise BadInput("Unknown capture challenge — start a new capture.")
    if row["used_at"]:
        raise BadInput("This capture challenge was already used.")
    issued = datetime.fromisoformat(row["issued_at"])
    if datetime.now(timezone.utc) - issued > timedelta(seconds=CHALLENGE_TTL_SECONDS):
        raise BadInput("Capture challenge expired — start a new capture.")
    db.execute(
        "UPDATE capture_challenges SET used_at = ? WHERE id = ?", (now_iso(), row["id"])
    )


# --------------------------------------------------------------------------
# Signature dispatch — the one place that knows both schemes exist
# (decisions/0004). Everything else in this module talks in terms of an
# algorithm name and opaque signature fields, not Schnorr or ECDSA specifics.
# --------------------------------------------------------------------------

def _verify(algorithm: str, public_key: str, message: str, sig_t: str, sig_s: str) -> bool:
    if algorithm == "schnorr":
        try:
            return _verify_schnorr(int(public_key), int(sig_t), int(sig_s), message)
        except (TypeError, ValueError):
            return False
    if algorithm == "ecdsa-p256":
        return crypto_ecdsa.verify_signature(public_key, sig_t, message)
    return False


# --------------------------------------------------------------------------
# Attestation (accept a device-signed manifest)
# --------------------------------------------------------------------------

def attest(db, *, handle: str, media_hash: str, captured_at: str, label: str,
           challenge: str, t: str, s: str = "", watermark_secret: str = "",
           manifest_id: str = "") -> dict:
    """Accept a signed capture manifest.

    `t` and `s` are the signature fields exactly as the signing scheme
    produced them: for Schnorr, two decimal-string components; for
    ecdsa-p256, `t` carries the full raw hex signature and `s` is unused.
    Which scheme applies is read from the enrolled device, not the request —
    a caller cannot claim a different algorithm than the device enrolled under.

    `watermark_secret` (decisions/0009) is the hex secret embedded into the
    capture BEFORE it was hashed and signed above, so `media_hash` already
    reflects the watermarked bytes — never generated here, never derived from
    anything else; the browser gets it from `/capture/watermark` first and
    just carries it through. Optional and nullable: a capture that skipped
    that step (or predates this feature) simply has no soft-binding fallback.

    `manifest_id` (decisions/0011) is normally reserved up front by
    `issue_challenge` and carried through unchanged — it has to be embedded
    in the file (decisions/0008) before the C2PA manifest is signed
    (decisions/0010), which is before this function ever runs. Falls back to
    generating a fresh one here only if a caller genuinely didn't have one
    (e.g. a capture that never touched the C2PA/PNG-metadata steps at all).
    """
    media_hash = (media_hash or "").strip().lower()
    handle = (handle or "").strip()
    label = (label or "").strip() or "unlabelled capture"
    captured_at = (captured_at or "").strip()
    challenge = (challenge or "").strip()
    t = (t or "").strip()
    s = (s or "").strip()
    watermark_secret = (watermark_secret or "").strip().lower() or None
    manifest_id = (manifest_id or "").strip().upper() or new_manifest_id()

    if not SHA256_RE.match(media_hash):
        raise BadInput("Invalid SHA-256 media hash.")
    if not captured_at:
        raise BadInput("A capture time is required.")
    if not challenge:
        raise BadInput("A capture challenge is required — captures must be live.")
    device = get_device(db, handle)
    if not device:
        raise BadInput("Unknown device — enrol it first.")
    if not t:
        raise BadInput("Malformed signature.")

    algorithm = device["algorithm"]

    # Burn the nonce first: a replayed or stale capture is rejected before we
    # spend time on crypto, and the nonce can never be reused.
    _consume_challenge(db, challenge)

    # Veridact verifies the DEVICE's signature; it never signs anything itself.
    message = manifest_message(media_hash, captured_at, handle, challenge)
    if not _verify(algorithm, device["public_key"], message, t, s):
        db.commit()  # keep the nonce burned even on failure
        raise InvalidSignature("Signature does not verify against the device key.")

    db.execute(
        """INSERT INTO manifests
           (manifest_id, device_id, media_hash, label, challenge, captured_at,
            received_at, sig_algorithm, sig_t, sig_s, watermark_secret)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (manifest_id, device["id"], media_hash, label, challenge, captured_at,
         now_iso(), algorithm, t, s, watermark_secret),
    )
    db.commit()
    return {
        "manifest_id": manifest_id,
        "device": handle,
        "media_hash": media_hash,
        "label": label,
        "captured_at": captured_at,
        "algorithm": algorithm,
    }


# --------------------------------------------------------------------------
# Soft-binding watermark (decisions/0009) — a pixel-processing step on the
# RAW frame, before it's ever hashed or signed. This function has no idea a
# signature will follow; it just embeds a fresh random secret and hands back
# the watermarked bytes for the browser to hash and sign instead of the
# original. It grants no trust by itself — see decisions/0009 §5.
# --------------------------------------------------------------------------

def start_capture_watermark(image_bytes: bytes) -> tuple[str, bytes]:
    secret = watermark.generate_secret()
    watermarked = watermark.embed(image_bytes, secret)
    return secret, watermarked


# --------------------------------------------------------------------------
# Verification (the four verdicts)
# --------------------------------------------------------------------------

def _manifest_verified(db, row) -> bool:
    """Re-check a stored manifest's signature against the device key (defensive)."""
    device = db.execute(
        "SELECT * FROM devices WHERE id = ?", (row["device_id"],)
    ).fetchone()
    if not device:
        return False
    message = manifest_message(row["media_hash"], row["captured_at"],
                               device["handle"], row["challenge"])
    return _verify(row["sig_algorithm"], device["public_key"], message,
                   row["sig_t"], row["sig_s"])


def verify(db, media_bytes: bytes, manifest_id: str | None = None) -> dict:
    """Verify a file. Hashes `media_bytes` itself (decisions/0009 — this used
    to take a client-computed hash; now it takes the actual file, because the
    watermark fallback below needs the real pixels, not just a hash string)."""
    media_hash = hashlib.sha256(media_bytes).hexdigest()

    row = db.execute(
        "SELECT * FROM manifests WHERE media_hash = ?", (media_hash,)
    ).fetchone()

    if row:
        device = db.execute(
            "SELECT * FROM devices WHERE id = ?", (row["device_id"],)
        ).fetchone()
        ok = _manifest_verified(db, row)
        return {
            "verdict": "VERIFIED_CAPTURE" if ok else "SIGNATURE_INVALID",
            "manifest_id": row["manifest_id"],
            "device": device["handle"] if device else "unknown",
            "label": row["label"],
            "media_hash": media_hash,
            "captured_at": row["captured_at"],
            "received_at": row["received_at"],
        }

    # No exact hash match. Before assuming ALTERED, check whether a soft-
    # binding watermark survives even though the exact bytes don't match —
    # decode-then-lookup (decisions/0009 §6): never trust "a watermark is
    # present" alone, only an EXACT match against a specific issued secret.
    decoded_secret = watermark.decode(media_bytes)
    if decoded_secret:
        wm_row = db.execute(
            "SELECT * FROM manifests WHERE watermark_secret = ?", (decoded_secret,)
        ).fetchone()
        if wm_row:
            device = db.execute(
                "SELECT * FROM devices WHERE id = ?", (wm_row["device_id"],)
            ).fetchone()
            return {
                "verdict": "RECOMPRESSED",
                "manifest_id": wm_row["manifest_id"],
                "device": device["handle"] if device else "unknown",
                "label": wm_row["label"],
                "media_hash": media_hash,
                "captured_at": wm_row["captured_at"],
            }

    # No manifest for this exact media, and no watermark match either. If a
    # manifest was referenced whose hash differs, the file changed since it
    # was signed -> ALTERED.
    manifest_id = (manifest_id or "").strip().upper()
    if manifest_id:
        ref = db.execute(
            "SELECT * FROM manifests WHERE manifest_id = ?", (manifest_id,)
        ).fetchone()
        if ref:
            device = db.execute(
                "SELECT * FROM devices WHERE id = ?", (ref["device_id"],)
            ).fetchone()
            return {
                "verdict": "ALTERED",
                "manifest_id": ref["manifest_id"],
                "device": device["handle"] if device else "unknown",
                "label": ref["label"],
                "signed_hash": ref["media_hash"],
                "actual_hash": media_hash,
                "captured_at": ref["captured_at"],
            }

    return {"verdict": "UNVERIFIED", "media_hash": media_hash}
