# 0011 — Fixing a real bug: the proof code was breaking C2PA validation

**Date:** 2026-08-07
**Status:** Accepted

## 1. The bug, as the founder actually found it

Reported directly from a real test capture, not caught in this project's own
testing first: taking a photo through Veridact, then checking that exact
file with the "check for C2PA credential" tool, showed **✗ INVALID C2PA
CREDENTIAL** — `assertion.dataHash.mismatch`, "hash verification (Hashes do
not match)." That is a real validation failure, not the expected/harmless
`signingCredential.untrusted` warning decisions/0010 already documents as
normal. Reproduced directly (not assumed) by signing a test PNG with
Veridact's own C2PA code, then adding the exact PNG metadata chunk
`static/pngtext.js` embeds (decisions/0008) on top of it: the previously-
valid file immediately started reading back `Invalid`, with the identical
error code and message the founder saw.

## 2. Root cause

Both decisions/0009 (the watermark) and decisions/0010 (the C2PA manifest)
already independently established the same rule: embedding into a file
changes its bytes, so embedding has to happen *before* Veridact hashes and
signs the file, never after — getting this backwards was caught and fixed
twice already in this project's own history.

**This was a third instance of the same class of bug, missed because it
crosses two separate pieces of work.** decisions/0008's proof-code chunk is
added by the *browser*, client-side, *after* `/attest` returns — because the
manifest id didn't exist until the server generated it during that call.
decisions/0010's C2PA manifest is embedded *before* signing, server-side.
Put those two individually-correct decisions next to each other and the
result is wrong: the proof-code chunk was landing **after** C2PA's manifest
was already signed. C2PA's own `c2pa.hash.data` assertion covers the file's
bytes as they exist at signing time — anything added afterward, even one
small metadata chunk nobody would think of as "editing" the photo, breaks
that hash. Every single capture with a C2PA manifest was affected; this
wasn't an edge case.

## 3. The fix: reserve the manifest id up front, embed in the right order

The manifest id no longer only exists after `/attest`. `issue_challenge`
(already the first server round-trip in the capture flow, decisions/0009 §5)
now also reserves a manifest id and returns it alongside the freshness
challenge — a plain random label, generated with the same
`util.new_manifest_id()` function `/attest` already used, just called
earlier. If a capture is abandoned partway through, that id simply never
gets written to the `manifests` table; nothing depends on every reserved id
being used, so there's no cleanup or gap to worry about.

The corrected embedding order, applied every capture: **watermark → proof
code → C2PA manifest → hash → sign → `/attest`.** The proof code now goes in
*before* C2PA, so C2PA's hash covers it and nothing is ever added to the
file afterward. `/attest` accepts the pre-reserved id and uses it instead of
minting a fresh one, so the id embedded in the file and the id in the
database are guaranteed to be the same value.

**Verified the fix directly, the same way the bug itself was reproduced:**
embedded the proof-code chunk into a plain PNG *first*, then signed it with
Veridact's C2PA code — reads back `validation_state: "Valid"`, no
`dataHash.mismatch`. Separately confirmed the proof code itself still
survives being embedded before C2PA touches the file (C2PA embedding
doesn't strip or relocate unrelated PNG chunks) — read back byte-for-byte
correct with the same reader `static/pngtext.js`'s server-side mirror
already uses.

## 4. Why this wasn't caught before shipping decisions/0010

Every automated test run before that decision was committed checked the
C2PA-embedded file's validity *before* the proof-code chunk was added on
top of it — because in the old order, the proof code was the very last step,
added by the browser after everything else. The test battery exercised
"is the C2PA manifest valid right after signing" and separately "does
Veridact's own VERIFIED_CAPTURE still work on the fully-assembled file" —
but never re-checked C2PA validity against the *actual final file* a user
would download and hand to a third-party checker. That gap is exactly what
a real end-to-end test, on a real capture, with a real check, caught that
the synthetic test battery didn't. Worth stating plainly rather than
smoothing over: this should have been one of the cases already covered, and
wasn't.

## 5. A second consequence of the reorder, caught by re-testing the fix itself

Moving the proof-code chunk to before signing fixed the C2PA bug, but broke
something else: `/api/verify` still stripped that chunk out before hashing,
which was the *correct* behavior under the old order (the chunk was added
after signing, so stripping it recovered the originally-signed bytes) and
became *wrong* the moment the chunk moved to before signing (the chunk is
now part of what was signed, so stripping it recovers bytes that were never
actually signed). Every fresh, untouched capture started reading back
**RECOMPRESSED instead of VERIFIED_CAPTURE** — caught immediately by
re-running the exact same end-to-end test used to confirm the C2PA fix,
not a separate bug report. Fixed by removing the strip entirely: `/api/verify`
now hashes exactly what was uploaded. `app/pngtext.py` (the server-side
stripping helper this depended on) is now dead code with no other caller,
and was removed rather than left behind describing a rationale that no
longer applies.

## 6. No change to what's proven

This is purely a reordering of embedding steps. Nothing about the
cryptography, the watermark's payload design, or the C2PA assertions
themselves changed — decisions/0009 and decisions/0010 remain accurate
descriptions of what each piece does and why. This document only corrects
the sequence they run in relative to each other.
