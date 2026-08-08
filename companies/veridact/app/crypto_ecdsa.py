"""
ECDSA P-256 verification — the peer-reviewed alternative to the custom Schnorr
construction in `crypto.py` (see decisions/0004).

Veridact still only ever *verifies*; it never generates or holds a private key.
The key generation and signing happen in the browser via the Web Crypto API
(`static/ecdsa.js`), using the exact same message format as the Schnorr path
(`media_hash | captured_at | handle | challenge`) so it plugs into the existing
freshness-challenge design (decisions/0003) unchanged.

Two real interoperability details, verified against genuine Web Crypto output
(not assumed from documentation) before this code was written:

1. Web Crypto's public key export (`format: "raw"`) is the SEC1 *uncompressed
   point* encoding: `0x04 ‖ X (32 bytes) ‖ Y (32 bytes)` — 65 bytes total for
   P-256. `cryptography`'s `EllipticCurvePublicKey.from_encoded_point` reads
   this directly.
2. Web Crypto's `subtle.sign()` output for ECDSA is the raw IEEE P1363
   format — `r ‖ s`, each a fixed 32 bytes for P-256 — **not** the ASN.1 DER
   encoding `cryptography`'s `verify()` expects. This must be converted with
   `encode_dss_signature` or every signature will fail to verify even though
   it is completely valid.

Reproduce the proof this module is built on: generate a keypair and sign with
Node's `crypto.webcrypto.subtle` (the same W3C implementation a real browser
uses — see decisions/0004 for the exact script), then verify the output here.
"""

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

CURVE = ec.SECP256R1()  # "P-256" in Web Crypto naming; this is the same curve


def load_public_key(pubkey_hex: str):
    """Parse a Web-Crypto-exported raw public key (hex-encoded)."""
    raw = bytes.fromhex(pubkey_hex)
    return ec.EllipticCurvePublicKey.from_encoded_point(CURVE, raw)


def verify_signature(pubkey_hex: str, signature_hex: str, message: str) -> bool:
    """Verify a raw-format ECDSA P-256 signature over `message` (UTF-8 encoded).

    `signature_hex` is the hex-encoded raw r‖s signature exactly as
    `crypto.subtle.sign()` produces it in the browser — no DER conversion
    needed on the caller's side; that happens here.
    """
    try:
        sig_raw = bytes.fromhex(signature_hex)
    except ValueError:
        return False
    if len(sig_raw) != 64:  # P-256: r and s are each 32 bytes
        return False
    r = int.from_bytes(sig_raw[:32], "big")
    s = int.from_bytes(sig_raw[32:], "big")
    sig_der = encode_dss_signature(r, s)

    try:
        public_key = load_public_key(pubkey_hex)
    except ValueError:
        return False

    try:
        public_key.verify(sig_der, message.encode(), ec.ECDSA(hashes.SHA256()))
        return True
    except InvalidSignature:
        return False
