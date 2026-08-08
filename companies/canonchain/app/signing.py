"""
The "wax seal": HMAC-SHA256 signing of registry records.

A signature binds a record's fields together under a secret key. If any stored
field is altered later, the recomputed signature won't match — so tampering is
detectable, and a Canonchain certificate becomes something you can hand to a
third party. (Production would move from one server secret to per-creator
keypairs; that's a swap of these functions, not the whole app — see ADR 0002.)
"""

import hashlib
import hmac
import secrets
from pathlib import Path


def load_signing_key(app) -> bytes:
    """Resolve the signing key: env var first, else a cached local dev file."""
    if app.config.get("SECRET_ENV"):
        return app.config["SECRET_ENV"].encode()
    path = Path(app.config["SECRET_FILE"])
    if path.exists():
        return bytes.fromhex(path.read_text().strip())
    key_hex = secrets.token_hex(32)
    path.write_text(key_hex)
    return bytes.fromhex(key_hex)


def sign_registration(key: bytes, registry_id: str, file_hash: str, filename: str,
                      description: str, handle: str, created_at: str,
                      leaf_index: int) -> str:
    # Sign EVERY field the certificate asserts, so altering any of them — the
    # filename, the description, the owner, the time — breaks the seal.
    msg = (f"{registry_id}|{file_hash}|{filename}|{description or ''}|"
           f"{handle}|{created_at}|{leaf_index}").encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def registration_signature_valid(key: bytes, row, handle: str) -> bool:
    expected = sign_registration(
        key, row["registry_id"], row["file_hash"], row["filename"],
        row["description"], handle, row["created_at"], row["leaf_index"],
    )
    return hmac.compare_digest(expected, row["signature"])


def sign_checkpoint(key: bytes, leaf_count: int, merkle_root: str) -> str:
    msg = f"{leaf_count}|{merkle_root}".encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()
