"""
Read and verify a real C2PA manifest embedded in an uploaded file — the
"interop" half of decisions/0007: Veridact reads the industry standard
(what Leica/Sony/Nikon/Canon/Samsung cameras already produce) rather than
inventing a competing one.

This uses the official `c2pa-python` library (contentauth/c2pa-rs's Python
bindings) to parse and cryptographically validate the manifest — no hand-rolled
JUMBF/COSE parsing here, on the same principle as everything else in this
project: never re-implement a peer-reviewed format yourself when an official
library exists.

**Why this needs the actual file, unlike Veridact's own scheme:** a C2PA
manifest is embedded *inside* the media file's own container (a JUMBF box
inside the JPEG/etc.), not a separate record keyed by a hash. There is no way
to check "does this file have a valid embedded manifest" from a hash alone —
the file's bytes have to be examined. This is a real, structural difference
from Veridact's own capture flow (decisions/0001, 0003), which deliberately
never uploads a file — kept as two clearly separate checks, not blended, so
Veridact's own privacy property isn't quietly weakened by this addition.

Verified against real data before being relied on here: the official test
fixture `C.jpg` (from contentauth/c2pa-python's own test suite) reads as
`validation_state: Valid`; a copy with one byte of pixel data flipped reads as
`Invalid`, with the specific reported reason `assertion.dataHash.mismatch —
Hashes do not match`.
"""

import json

import c2pa


class C2paReadError(Exception):
    pass


def read_manifest(file_path: str) -> dict:
    """Read and validate any C2PA manifest embedded in the file at `file_path`.

    Returns a plain-dict summary safe to serialize straight to JSON — never the
    raw library objects, so the API response shape doesn't depend on the
    library's internal representation.
    """
    try:
        with c2pa.Reader(file_path) as reader:
            data = json.loads(reader.json())
            validation_state = reader.get_validation_state()
    except c2pa.C2paError as e:
        raise C2paReadError(f"No readable C2PA manifest ({type(e).__name__}: {e})")

    active = data.get("active_manifest")
    manifests = data.get("manifests", {})
    m = manifests.get(active, {}) if active else {}

    # `claim_generator` (a flat string) is the older V1 manifest field; current
    # c2pa-python/c2pa-rs defaults to V2 claims, which carry the same
    # information as `claim_generator_info` (a list of {name, version, ...})
    # instead. Read whichever is actually present rather than assuming V1 —
    # caught by testing this reader against a manifest this project's own
    # C2PA-writing code produces (decisions/0010), not just the V1-format
    # official test fixture this module was originally verified against.
    claim_generator = m.get("claim_generator")
    if not claim_generator:
        info = m.get("claim_generator_info") or []
        claim_generator = ", ".join(
            f"{i.get('name', '?')}/{i.get('version', '?')}" for i in info
        ) or None

    return {
        "has_manifest": bool(active),
        "validation_state": validation_state,  # "Valid" | "Invalid" | "Trusted" (library-defined states)
        "validation_status": data.get("validation_status", []),
        "claim_generator": claim_generator,
        "title": m.get("title"),
        "format": m.get("format"),
        "signature_info": m.get("signature_info"),
        "assertions": [a.get("label") for a in m.get("assertions", [])],
    }
