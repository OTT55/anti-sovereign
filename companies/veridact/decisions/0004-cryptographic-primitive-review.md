# 0004 — Cryptographic primitive review: Schnorr/RFC3526 vs. ECDSA P-256 vs. WebAuthn

**Date:** 2026-07-25
**Status:** Accepted (ECDSA P-256 added as a peer-reviewed signing option) —
WebAuthn scoped as a follow-up experiment, not yet implemented.

## 1. The problem, and why it matters

Decision 0002 chose a custom Schnorr construction over the RFC 3526 2048-bit
MODP group because, at the time, this environment could not install the
`cryptography` package (offline, broken package cache) and the Schnorr code was
"already implemented and end-to-end verified in this repo" via Nullform. That
was the right call under that constraint — a working, self-contained, correctly
verified system beats a blocked attempt at a "better" one.

Two real gaps were flagged against that choice in this project's own research
review (`research/02-veridact.md`):

1. The implementation reduces exponents modulo the full group order `p − 1`
   rather than a prime-order subgroup — a known simplification, not an
   independently peer-reviewed construction for this specific use.
2. Enrolment generates a private key **in JavaScript** and displays it to the
   user as text to save — meaning the key can be copied, logged, screenshotted,
   or leaked by anything with access to the page, and nothing prevents the user
   from reusing it carelessly.

Veridact's entire premise is that a signature proves genuine device origin.
Both gaps weaken that premise in ways worth closing with peer-reviewed,
standard primitives rather than continuing to reason from first principles
about a bespoke construction.

## 2. What changed since decision 0002

Re-tested today: `pip install cryptography`, `pip install pyopenssl`, and
`pip install fido2` **all succeeded** in this environment. The constraint that
justified staying with custom Schnorr no longer holds. This is exactly the kind
of "revisit conclusions when new evidence appears" case a rigorous process
should catch, rather than leaving yesterday's blocker as today's permanent
architecture.

## 3. Survey of real, peer-reviewed alternatives

| Option | What it is | Peer-reviewed / standardized? | Browser support | Where the private key lives |
|---|---|---|---|---|
| **Schnorr / RFC3526** (current) | Custom Fiat–Shamir Schnorr over a Diffie-Hellman MODP group | The Schnorr protocol itself, yes (1991, decades of analysis); *this specific application* (full group order, not a prime-order subgroup) is not an independently reviewed construction | Requires hand-written `BigInt` code (as already built) | Generated in JS, shown to the user as text |
| **Ed25519** | EdDSA over Curve25519 (RFC 8032) | Yes — one of the most widely reviewed modern signature schemes | Inconsistent: added to Web Crypto in recent Chrome/Firefox versions, absent or partial in others as of this review | Same exposure risk as Schnorr unless paired with WebAuthn |
| **ECDSA P-256** | NIST P-256 curve, FIPS 186-4 | Yes — the most widely deployed signature scheme in the world (TLS, WebAuthn/passkeys, most PKI) | **Universal** — supported in every evergreen browser's Web Crypto API for years | Same exposure risk as Schnorr, *unless* the key is generated `extractable: false` |
| **WebAuthn (platform authenticator)** | W3C standard; the credential itself is typically ECDSA P-256 or Ed25519 under the hood, but key generation/storage/signing all happen inside OS-managed secure hardware | Yes — W3C Recommendation, the same standard behind passkeys | Universal on modern OSes (Face ID/Touch ID on iPhone, StrongBox/TEE on Android, Windows Hello/TPM on Windows) | **Never leaves secure hardware** — not even the browser's JS can read it out |

## 4. Recommendation, with confidence levels

**High confidence: adopt ECDSA P-256 as an additional, peer-reviewed signing
option now.** It requires no new server dependency risk beyond what was just
proven to install, has zero browser-compatibility risk (unlike Ed25519), and
directly replaces the one genuinely unreviewed part of the current
construction (the ad-hoc group-order choice) with the world's most
battle-tested signature scheme. **Verified today, not assumed:** a real
ECDSA P-256 signature produced by Node's actual Web Crypto implementation (the
same W3C API a browser exposes, not a simulation) was independently verified
in Python using the `cryptography` library, including a negative control
(a tampered message correctly failed verification). The one real implementation
detail this surfaced: **Web Crypto emits a raw `r ‖ s` signature (IEEE P1363),
while Python's `cryptography` library expects ASN.1 DER** — the conversion
(`encode_dss_signature`) is a few lines, but it is the kind of interoperability
detail that would silently produce "signature invalid" errors if missed, and
is exactly why this was verified with real data rather than assumed correct
from documentation.

**Medium confidence, staged as an experiment rather than adopted now: WebAuthn
platform authenticators for device enrolment.** This is the construction that
actually solves gap #2 above — the private key would never exist in JavaScript
at all, closing the "extracted software key" risk stated explicitly in
decision 0003 as V1's known limitation, without waiting for camera
manufacturers to add on-sensor signing. The `fido2` package (Yubico's
widely-used open-source FIDO2/WebAuthn server library) now installs cleanly,
removing the prior blocker here too. This is *not* implemented in this pass —
the added complexity (CBOR/COSE key parsing, attestation object formats,
platform-specific quirks) is real, and the correct next step per a disciplined
process is a scoped prototype, not a same-day production cutover of a working
system. **What it does not solve:** WebAuthn secures *key custody*
("no one can extract this credential"), not *capture authenticity*
("this came from a real camera, not OBS") — those remain the two distinct
problems decision 0003 already correctly separates, and WebAuthn only closes
the first one.

**Not adopted: Ed25519 directly.** The signature scheme itself is excellent;
the practical blocker is inconsistent browser Web Crypto support today, which
would force a JS-side polyfill and reintroduce exactly the kind of
"do we trust this specific non-native implementation" question ECDSA P-256's
universal native support avoids entirely.

## 5. What was actually built this pass (see the code, not just this document)

- `app/crypto_ecdsa.py` — server-side verification using the `cryptography`
  library: parses a raw uncompressed EC point public key, converts a raw
  Web-Crypto-format signature to DER, verifies against SHA-256, with the
  interoperability handled and tested (see `tests/` in that module's
  docstring for how to reproduce the Node-generated proof independently).
- `static/ecdsa.js` — client-side key generation and signing via
  `crypto.subtle`, mirroring `static/device.js`'s existing message format
  (`media_hash | captured_at | handle | challenge`) so it plugs into the
  existing freshness-challenge design from decision 0003 unchanged.
- `devices.algorithm` and `manifests.sig_algorithm` columns added to the
  schema (default `'schnorr'` for every existing row, so nothing already
  enrolled breaks) — new enrolments can specify `ecdsa-p256`; the API
  dispatches to the matching verifier.

## 6. Complexity and risk, stated plainly

- **Complexity of what shipped:** low–medium. The verification math is a
  handful of lines once the raw-signature/raw-point conversions are correct;
  the schema change is additive and backward-compatible.
- **Complexity of the WebAuthn follow-up, if pursued:** medium–high. Expect a
  multi-day spike, not an afternoon, given CBOR parsing and
  attestation-format handling — correctly deferred rather than rushed.
- **Risk of what shipped:** low. It does not remove or alter the existing
  Schnorr path; both are tested independently and dispatch is explicit per
  device, so nothing already working can regress.
- **Open question for the founder, not resolved here:** whether to make
  `ecdsa-p256` the default for *new* enrolments now, keep offering both, or
  wait for a WebAuthn prototype before changing the default at all. This
  document recommends making ECDSA P-256 the default for new enrolments (it
  is strictly better-reviewed with no compatibility cost) while leaving
  Schnorr enrolment available and fully supported for anything already
  enrolled.
