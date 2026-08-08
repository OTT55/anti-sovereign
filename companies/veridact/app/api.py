"""
JSON API: enrol a device, submit a device-signed manifest, verify media.

Veridact verifies signatures here; it never creates them. The device's private
key stays in the browser.
"""

import os
import tempfile

from flask import Blueprint, Response, jsonify, request

from .c2pa_check import C2paReadError, read_manifest
from .c2pa_sign import embed_manifest
from .db import get_db
from .manifests import (
    BadInput, DuplicateHandle, InvalidSignature, attest, enrol_device,
    get_device, issue_challenge, start_capture_watermark, verify,
)

bp = Blueprint("api", __name__)


@bp.get("/capture/challenge")
def challenge_route():
    """Issue a one-time nonce the capture agent folds into its signature, so the
    capture is provably live rather than pre-computed (decisions/0003)."""
    return jsonify(issue_challenge(get_db()))


@bp.post("/capture/watermark")
def capture_watermark_route():
    """Embed a fresh soft-binding watermark into a raw captured frame, BEFORE
    it's hashed and signed (decisions/0009 §5 — order matters: watermarking
    after signing would mean the saved file could never hash-match what was
    signed again).

    This route proves nothing by itself and requires no device/signature —
    it's a generic "embed a random secret, return the secret and the image"
    step. Trust still comes entirely from `/attest`'s signature check; a
    secret embedded here means nothing until it's attached to a successfully
    signed manifest there.
    """
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify(error="No frame provided."), 400

    secret, watermarked = start_capture_watermark(file.read())
    return Response(
        watermarked, mimetype="image/png",
        headers={"X-Watermark-Secret": secret},
    )


@bp.post("/capture/c2pa")
def capture_c2pa_route():
    """Embed a real, industry-standard C2PA manifest into a captured frame,
    signed with Veridact's own certificate — the "write" half of
    decisions/0007's interop story (decisions/0010).

    Same ordering rule as /capture/watermark: this MUST happen before
    hashing/signing Veridact's own manifest, because embedding changes the
    file's bytes. Assertions cover only what's actually known at this point
    in the flow — captured_at and challenge are passed in because the
    browser fetches the freshness challenge before this call now, precisely
    so this route can honestly assert them (decisions/0010).
    """
    file = request.files.get("file")
    handle = (request.form.get("handle") or "").strip()
    captured_at = (request.form.get("captured_at") or "").strip()
    challenge = (request.form.get("challenge") or "").strip()
    if not file or not file.filename:
        return jsonify(error="No frame provided."), 400
    if not handle or not get_device(get_db(), handle):
        return jsonify(error="Unknown device — enrol it first."), 400
    if not captured_at or not challenge:
        return jsonify(error="Missing capture timestamp or challenge."), 400

    signed = embed_manifest(
        file.read(), device_handle=handle, captured_at=captured_at, challenge=challenge,
    )
    return Response(signed, mimetype="image/png")


@bp.post("/enroll")
def enroll_route():
    data = request.get_json(silent=True) or {}
    try:
        handle = enrol_device(
            get_db(), data.get("handle"), data.get("public_key"),
            algorithm=data.get("algorithm"),
        )
    except DuplicateHandle as e:
        return jsonify(error=str(e)), 409
    except BadInput as e:
        return jsonify(error=str(e)), 400
    return jsonify(handle=handle)


@bp.post("/attest")
def attest_route():
    data = request.get_json(silent=True) or {}
    try:
        manifest = attest(
            get_db(),
            handle=data.get("handle"),
            media_hash=data.get("media_hash"),
            captured_at=data.get("captured_at"),
            label=data.get("label"),
            challenge=data.get("challenge"),
            t=data.get("t"),
            s=data.get("s"),
            watermark_secret=data.get("watermark_secret"),
            manifest_id=data.get("manifest_id"),
        )
    except InvalidSignature as e:
        return jsonify(error=str(e)), 422
    except BadInput as e:
        return jsonify(error=str(e)), 400
    return jsonify(manifest)


@bp.post("/api/verify")
def verify_route():
    """Verify a file. Takes the actual upload now, not just a hash string
    (decisions/0009) — the watermark fallback needs real pixels to decode,
    not something a hash alone could ever provide, the same structural reason
    /api/verify/c2pa already needs the file rather than a hash (decisions/0007).
    """
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify(error="Choose a file to verify."), 400

    # Hash exactly what was uploaded — no stripping. The proof-code PNG chunk
    # (decisions/0008) is now embedded BEFORE the C2PA manifest and before
    # signing (decisions/0011), so it's part of what was actually signed, not
    # something added afterward. Stripping it here would recover the WRONG
    # bytes and break VERIFIED_CAPTURE on every untouched capture — exactly
    # the regression decisions/0011 fixed; do not reintroduce it.
    media_bytes = file.read()

    try:
        result = verify(get_db(), media_bytes, request.form.get("manifest_id"))
    except BadInput as e:
        return jsonify(error=str(e)), 400
    return jsonify(result)


@bp.post("/api/verify/c2pa")
def verify_c2pa_route():
    """Check a file for a real, industry-standard C2PA manifest — the kind a
    Leica, Sony, or Samsung Galaxy S26 embeds at capture (decisions/0007).

    Unlike /api/verify above, this route needs the actual file: a C2PA
    manifest lives inside the file's own container, not in a separate
    hash-keyed record, so there is no way to check it from a hash alone. This
    is a deliberate, narrow exception to Veridact's own never-upload rule
    (decisions/0001, 0003) for its own capture scheme — the two checks stay
    clearly separate rather than blended.
    """
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify(error="Choose a file to check."), 400

    # A real temp file, not a BytesIO: the c2pa library reads by path/container
    # format, and is deleted immediately after the check either way.
    suffix = os.path.splitext(file.filename)[1] or ".bin"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as fh:
            file.save(fh)
        result = read_manifest(tmp_path)
    except C2paReadError:
        return jsonify(has_manifest=False)
    finally:
        os.remove(tmp_path)

    return jsonify(result)
