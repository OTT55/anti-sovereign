# 0010 — Writing real C2PA manifests at capture time, not just reading them

**Date:** 2026-08-03
**Status:** Accepted

## 1. The problem

Decision 0007 gave Veridact the ability to *read* another system's C2PA
credential — a Leica's, a Sony's, an Instagram-stripped one. It never gave
Veridact the other half: emitting its own. Anyone checking a Veridact capture
with a third-party tool (Adobe's own C2PA verifier, a browser extension, any
other C2PA-aware software) saw nothing at all, because Veridact never wrote
anything into the file's own container — only its separate hash-keyed
manifest table, which only Veridact itself can look up.

## 2. Decision

Embed a real C2PA manifest into every capture, built and signed with the
same official `c2pa-python` library decision 0007 already reads with —
`Builder` + `Signer.from_info` + `Builder.sign_file`, not hand-rolled
JUMBF/COSE construction, the same established-library principle as the rest
of this project (decisions/0002, 0007, 0009).

**Assertions cover exactly what the capture flow actually establishes** —
nothing asserted that isn't backed by something real:

- `c2pa.actions`: one `c2pa.created` action with `digitalSourceType`
  `http://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture` — the
  IPTC-defined term specifically for "digital capture sampled from real
  life," confirmed via IPTC's own current documentation, not assumed. (The
  library's own example uses `digitalCreation`, the term for AI/software
  generation — the wrong one for this project; easy to copy by accident,
  caught by checking rather than reusing the example verbatim.)
- `veridact.capture` (a Veridact-specific assertion label): `captured_at`,
  `device` (the enrolled handle), and `challenge` (the one-time freshness
  nonce, decisions/0003) — the three pieces of evidence this flow actually
  has. Nothing about pixel content, location, or anything else not directly
  observed is asserted.

## 3. Veridact signs with its own certificate — a second kind of key

Decision 0002's "Veridact holds no signing secret" was specifically about
*device attestation*: Veridact verifies a device's signature, never produces
one on a device's behalf. C2PA writing is a different relationship —
Veridact is the party vouching for what it directly observed (much like a
camera manufacturer's own signing key vouches for its camera's output), so
**Veridact now holds a second, separate signing key**, used only for this.

A self-signed certificate (`app/c2pa_sign.py`, EC P-256, generated once and
persisted — `.gitignore`d, regenerated automatically on first run in a new
environment) rather than the library's bundled test fixture. Reusing the
official test fixture would mean every Veridact capture showed up signed by
the same generic "C2PA Test Signing Cert" every other developer testing
against this library also uses — a self-signed "Veridact" identity is more
honest about who actually signed it, even though (§5) it isn't yet
independently trusted by anyone.

## 4. Two real implementation gotchas, found by testing before shipping

1. **A self-signed certificate without a `SubjectKeyIdentifier` extension
   was rejected outright** — `c2pa.C2paError.Signature: "the certificate is
   invalid"` — before any assertion data was even considered. Fixed by
   comparing against the official test fixture's own certificate structure
   (`contentauth/c2pa-python`'s `tests/fixtures/es256_certs.pem`, fetched
   and inspected directly) and matching its extension set: `BasicConstraints`,
   `KeyUsage` (digital signature + content commitment), `ExtendedKeyUsage`
   (`emailProtection` — the same EKU the official test cert uses, kept for
   consistency rather than guessed at), plus `SubjectKeyIdentifier` and
   `AuthorityKeyIdentifier` (self-referential, since this cert is its own
   issuer).
2. **A timestamp authority is not optional in this library version** —
   passing an empty `ta_url` doesn't skip timestamping; it fails signing
   entirely with an opaque `C2paError.Signature: "empty string"`. Fixed by
   using a real public RFC 3161 timestamp server
   (`http://timestamp.digicert.com`, the same one the library's own official
   example uses) rather than omitting it. **Real consequence worth stating
   plainly:** every capture's C2PA embedding step now has a genuine external
   network dependency, on a third party this project doesn't control. If
   that timestamp server is slow or unreachable, C2PA embedding — one step
   in the capture pipeline, ahead of Veridact's own signing — fails for that
   capture. Not addressed further in this pass; worth revisiting if this
   becomes a real reliability problem (a fallback timestamp server, or
   making this step skip-and-continue rather than hard-fail, are both
   reasonable future options).

## 5. What "genuinely valid" does NOT mean here — stated plainly, not overstated

**The manifest this produces is real and correctly signed the moment this
ships.** Verified against actual files, both ways, using Veridact's own
reader (`app/c2pa_check.py`, updated below): a capture signed this way reads
back `validation_state: "Valid"`, with the `veridact.capture` assertion
(captured_at/device/challenge) intact and readable; flipping one byte of the
signed file correctly reads back `validation_state: "Invalid"`, with the
specific reason `assertion.hashedURI.mismatch`.

**What it does not mean: "Trusted" in someone else's C2PA validator.** Every
reading of a Veridact-signed file — by this project's own reader or any
other C2PA-aware tool — currently reports `signingCredential.untrusted`,
because Veridact's certificate isn't on the official C2PA trust list. That
is a **registration process** (submitting Veridact's certificate/identity to
the Content Authenticity Initiative's trust list program), not a code change,
and this work does not attempt it. Until that registration happens, the
honest claim is: *this manifest is genuinely, cryptographically valid and
was really signed by Veridact* — not *"a recognized, trusted authority
signed this,"* which is a separate, later step. Nothing in the UI should
imply "Trusted everywhere" before that registration is real.

## 6. A small, necessary fix to the reader this surfaced

`app/c2pa_check.py` only extracted the older, flat `claim_generator` string
field. The library's own current example notes "claims version 2 is the
default" — and V2 claims carry `claim_generator_info` (a list of
`{name, version}`) instead. Signing with the current library defaults (as
this decision does) produced a manifest the existing reader read back as
`claim_generator: null` — not a bug in the *signing* side, but a real gap in
the *reading* side that this project's own new manifests exposed. Fixed by
falling back to `claim_generator_info` when the flat field isn't present;
re-verified the original V1-format official test fixture (`C.jpg`,
decisions/0007) still reads identically afterward — no regression.

## 7. Ordering: the same lesson from decisions/0009, applied again

C2PA embedding changes the file's bytes (JUMBF is embedded directly into the
container), exactly like the watermark. It embeds **before** hashing and
signing Veridact's own manifest, in the same pre-sign pipeline decision 0009
already established, chained after the watermark step: raw frame → embed
watermark → embed C2PA manifest → hash → sign → `/attest`. Getting this
order wrong a second time — embedding after signing — would repeat exactly
the bug caught and fixed in 0009 (a freshly-saved capture could never
hash-match what was signed). Because the C2PA assertions need
`captured_at`/`challenge` as honest evidence, the freshness challenge is now
fetched and the capture timestamp set *before* both embedding steps, not
immediately before signing as in 0009's version — still single-use and
short-lived (decisions/0003); the embedding round-trips take well under a
second combined, nowhere near the challenge's TTL.

## 8. Relationship to the rest of this project

This is **interoperability** (decisions/0007's other half — readable by
outside tools) — **not durability** (decisions/0009's watermark, surviving
recompression). A C2PA manifest embedded here is stripped by lossy resharing
exactly like a Leica's or Sony's is; the watermark is what's still checkable
afterward. The two are complementary and independent: this ships without
touching the watermark's design, and the watermark still matters exactly as
much after this ships.
