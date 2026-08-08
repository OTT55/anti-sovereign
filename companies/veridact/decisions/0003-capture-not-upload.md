# 0003 — Veridact captures; it does not accept uploads

**Date:** 2026-07-22
**Status:** Accepted — supersedes the file-upload attest flow shipped in Phase 1

## Context

Phase 1's "Authenticate" page let the user **pick any file already on their disk**
and sign it. The founder caught the flaw immediately:

> "I can create an AI image and [claim] this was done on my phone."

He is right, and it invalidates the product's core claim. Signing a
user-chosen file proves only:

> *an enrolled device signed these bytes*

It does **not** prove:

> *this device captured this footage*

Those are different statements. Generate an AI video, save it, sign it with your
enrolled key, and Phase 1 would have stamped it **VERIFIED CAPTURE**. That is
precisely the "guess dressed as a proof" that ADR 0001 promised we'd never ship.

## Decision

**Veridact operates the camera itself and signs frames at the moment of capture.
The attest flow accepts no user-selected files.**

1. **Live capture only.** The Authenticate page opens the camera (`getUserMedia`),
   shows a live preview, and captures the frame directly into memory. The bytes are
   hashed and signed without ever existing as a file the user could substitute.
   There is no file picker in the attest path.
2. **Server-issued freshness challenge.** Before capture, the browser requests a
   one-time random challenge from Veridact. That challenge is included in the signed
   message and can be used once, within a short window. This binds the signature to
   *"a capture that happened just now, in a session Veridact opened"* — you cannot
   pre-compute a signature or replay an old one.
3. **File upload remains on `/verify` only.** Verification *must* accept a file:
   someone checking footage they received needs to hash it. Accepting a file to
   *check* it is safe; accepting a file to *attest* it is not. The asymmetry is the
   whole point.

## Why this is the right cut

Attestation is only meaningful if there is **no gap between the sensor and the
signature** where content can be substituted. Every gap is an attack. The file
picker was a gap wide enough to drive the entire threat model through. Capturing
in-page closes it: the user never chooses the bytes, so they cannot supply
generated ones.

## Trade-off — the gap that remains (stated honestly)

Browser capture closes the "sign any file on disk" hole. It does **not** close
everything:

- **Virtual cameras.** Software like OBS can present a synthetic video stream as if
  it were a webcam. The browser cannot tell a real sensor from a virtual one, so a
  determined attacker could still feed AI content into a "live" capture.
- **The real fix is hardware.** Only a camera whose secure chip signs frames on the
  sensor itself removes this. That is the documented endgame (ADR 0001) and the
  direction of C2PA.

**So V1's honest claim is narrower than "this is definitely real":** it is *"this
was captured live through Veridact's capture agent by an enrolled device, and has
not changed since."* That is a real, checkable statement — and strictly stronger
than what the upload flow could say. We state the virtual-camera limit in the UI
and the README rather than letting the VERIFIED CAPTURE badge imply more than it
proves.
