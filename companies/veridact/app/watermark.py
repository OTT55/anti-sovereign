"""
Soft-binding watermark: TrustMark (Adobe's Content Authenticity Initiative
library — the same organization behind the C2PA spec `app/c2pa_check.py`
already depends on). See decisions/0009 for why, and the real, verified
robustness/payload findings this module's design is built on.

Two things this module deliberately does NOT do:
- It does not decide what a decode "means." `decode()` returns whatever bits
  came out, even garbage from an image that was never watermarked at all
  (decisions/0009 §3) — the caller MUST look that value up against a specific
  stored secret and only trust an exact match. Presence alone proves nothing.
- It does not touch signing. Embedding happens on the RAW frame, before
  hashing and signing (decisions/0009 §5) — this module has no idea a
  signature exists at all.
"""

import io
import secrets
import threading

from PIL import Image
from trustmark import TrustMark

# 56 bits (7 bytes) — comfortably under the default BCH_5 scheme's 61-bit
# usable capacity (TrustMark's headline "100 bits" includes ECC overhead and
# is NOT the usable payload — verified against the library's own source,
# decisions/0009 §7, after a naive ASCII payload silently corrupted).
SECRET_BYTES = 7

_tm = None
_tm_lock = threading.Lock()


def _model() -> TrustMark:
    """Load the model once per process, not per request. First call is slow
    (model download/load, decisions/0009 §9); loadRemover/loadBBoxDetector are
    disabled because Veridact only ever encodes and decodes, never removes a
    watermark or auto-detects a crop region — verified this doesn't affect
    encode/decode correctness before relying on it."""
    global _tm
    if _tm is None:
        with _tm_lock:
            if _tm is None:
                _tm = TrustMark(
                    model_type="Q", verbose=False,
                    loadRemover=False, loadBBoxDetector=False,
                )
    return _tm


def generate_secret() -> str:
    """A fresh random secret for one capture. Hex-encoded (14 chars) for easy
    storage/indexing — never derived from the manifest ID, which is public."""
    return secrets.token_hex(SECRET_BYTES)


def _hex_to_bits(hex_str: str) -> str:
    return "".join(format(b, "08b") for b in bytes.fromhex(hex_str))


def _bits_to_hex(bits) -> str:
    bits = "".join(str(int(b)) for b in bits[: SECRET_BYTES * 8])
    n = (len(bits) // 8) * 8
    return bytes(int(bits[i:i + 8], 2) for i in range(0, n, 8)).hex()


def embed(image_bytes: bytes, secret_hex: str) -> bytes:
    """Embed `secret_hex` into the image's pixels. Returns a new PNG's bytes —
    call this BEFORE hashing/signing (decisions/0009 §5), never after."""
    cover = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    watermarked = _model().encode(cover, _hex_to_bits(secret_hex), MODE="binary")
    out = io.BytesIO()
    watermarked.save(out, format="PNG")
    return out.getvalue()


def decode(image_bytes: bytes) -> str | None:
    """Best-effort decode. Returns a hex string that may be meaningless noise
    (decisions/0009 §3) — the caller must look it up against a real stored
    secret and only trust an exact match. Returns None if the bytes aren't a
    readable image at all (not an error — just nothing to check)."""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        return None
    bits, _present, _schema = _model().decode(img, MODE="binary")
    return _bits_to_hex(bits)
