# Veridact — Truth Infrastructure

**Sovereign Stack company #1 · Category: Truth Infrastructure**
**Status: first production app of the Sovereign Stack — Phase 1 complete.**

Veridact answers one question: **was this video actually captured by a real
camera, or generated?**

It answers it by **proving origin**, not by guessing. Veridact never analyses
pixels to decide whether something "looks AI." It checks a cryptographic
signature made by the capture device at the moment of recording. Either that
proof exists and checks out, or it doesn't — there is no probability involved.

## The four honest verdicts

| Verdict | Meaning |
|---|---|
| **VERIFIED CAPTURE** | Signed by an enrolled device and unaltered since capture. This is a real capture. |
| **RECOMPRESSED** | The exact bytes don't match what was signed, but a soft-binding watermark embedded at capture time was found intact — the content is very likely unchanged, just re-encoded somewhere along the way (WhatsApp, Messenger, a resize). Honestly weaker than VERIFIED CAPTURE, honestly different from ALTERED (decisions/0009). |
| **ALTERED** | It came from a known device, but the file changed after signing — edited, re-encoded, or AI-processed. |
| **UNVERIFIED** | No capture proof exists for this file. It may be AI, or simply from a camera that doesn't sign. **Veridact makes no claim either way.** |

That last row is the product. A competitor would bluff "likely fake." Veridact
says "I can't prove this one" — because a truth-infrastructure company that
overstates its evidence has nothing to sell. Veridact proves things are **real**;
it never claims something is fake.

## Where this fits in a real, already-crowded market

Live research (not assumed — see [research/13](../../research/13-veridact-competitive-landscape.md))
found this space moving fast: **C2PA**, the industry content-provenance
standard, is now built directly into camera *hardware* (Leica, Sony, Nikon,
Canon, Samsung), and **Truepic**, a C2PA founding member, has raised $39.1M
behind Microsoft/Adobe/Sony's venture arms doing exactly this for
insurance/lending. Competing head-on with a funded hardware standard on "we can
sign a photo" alone isn't realistic.

So Veridact's stated direction ([decisions/0007](decisions/0007-positioning-interop-not-competition.md)):
**interoperate with C2PA rather than invent a competing standard**, and aim at
people the funded players don't serve — small law firms and individuals
documenting a real dispute, not insurers or international human-rights bodies
(who already have a credible, decade-old nonprofit tool in eyeWitness to
Atrocities). Veridact's own signing (below) remains genuinely useful as the
bridge for the many devices — most phones, today — that don't have C2PA
hardware support yet.

**The interop half is built, not just planned:** the Verify page can also
check a file for a real, camera-issued C2PA credential (Leica/Sony/Nikon/
Canon/Samsung's own hardware signing), using the official `c2pa-python`
library — not a hand-rolled parser. Verified against the library's own real
test fixture: an unmodified signed image reads as `Valid` with the actual
signing certificate and timestamp; a single flipped byte reads as `Invalid`
with the specific reason (`Hashes do not match`). See
[decisions/0007](decisions/0007-positioning-interop-not-competition.md) §5.

## How it works

1. **Enrol a device.** The browser generates a keypair. The **private key never
   leaves the device**; only the public key is sent to Veridact.
2. **Capture & sign — Veridact operates the camera.** There is **no file picker**
   in this flow. Veridact opens the camera, and the instant you capture, the frame
   is hashed and signed in memory. The capture is bound to a **one-time challenge**
   Veridact issued seconds earlier, so the signature is provably *live* — it can't
   be pre-computed or replayed.
3. **Verify.** Anyone can re-hash a file. Veridact looks for a matching manifest
   and checks the signature against the device's public key.

### Why there's no "upload a file to sign" button

Signing a file the user chooses proves only *"an enrolled device signed these
bytes"* — **not** *"this device captured this footage."* You could generate an AI
image, sign it, and get a VERIFIED CAPTURE badge. That gap makes the entire product
meaningless, so the attest path never accepts user-supplied files. Uploading is
allowed **only on `/verify`**, where you're *checking* content rather than
*vouching* for it. See [decisions/0003](decisions/0003-capture-not-upload.md).

## Why the signatures are asymmetric (this is the important part)

Veridact stores **only public keys**. Public keys can *check* a signature but
cannot *create* one.

This means Veridact **cannot forge a capture proof — even for itself.** If
Veridact were breached tomorrow, or an insider went rogue, there is nothing on the
server that could mint a "verified real" stamp for an AI video. The trust is
anchored at the device, which is where "it's real" actually originates.

(The earlier MVP used HMAC — one shared secret held by the server. That can prove
a record wasn't edited, but not *who* made it, because the server could have signed
it. Fixing that is the single most important upgrade in V1. See
[decisions/0002](decisions/0002-signatures.md).)

Two signing schemes are supported, chosen per device at enrolment:

- **ECDSA P-256** (the default for new enrolments) — the world's most widely
  deployed signature scheme (TLS, WebAuthn/passkeys, most PKI), signed and
  verified using the browser's native `crypto.subtle` and Python's
  `cryptography` library. No custom math anywhere in this path.
- **Schnorr over a 2048-bit MODP group** (RFC 3526, group 14) — this project's
  original scheme, kept fully supported for anything already enrolled under it.
  The device signs with private key `x`; Veridact verifies with public key
  `y = gˣ mod p`. Zero dependencies, runs in every browser via `BigInt`.

Decision 0002 explains why Schnorr was chosen first (the peer-reviewed
libraries weren't installable in this environment at the time); decision 0004
records what changed, why ECDSA P-256 is now the better default, and why a
future move to WebAuthn (hardware-backed keys, not just a hardware-independent
signature scheme) is the next real upgrade beyond this one.

## Honest limits of V1

Stated openly rather than oversold:

- **The device key lives in software**, so a determined attacker who extracts it
  could sign a fake as a real device. Moving the key into camera hardware (a secure
  enclave) is the documented next step — everything else about the protocol is
  already the real thing.
- **Attestation only helps content that was signed at capture.** Most video in the
  world isn't signed yet, so it lands in UNVERIFIED. That's the honest answer, and
  the same bootstrap every provenance standard (including C2PA) faces.

## How to run locally

```bash
cd companies/veridact
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
python run.py
```

Open <http://127.0.0.1:5102>. (Set `VERIDACT_PORT` to change the port.)

1. **Enrol device** — pick a signing scheme (ECDSA P-256 is the default),
   generate a keypair in your browser, and save the private key.
2. **Capture** — enter your handle + private key, **Start camera**, then
   **Capture & sign**. Download both the image and its manifest.
3. **Verify** — drop that downloaded image in to get VERIFIED CAPTURE. Edit it in
   any way and verify again with the manifest ID to get ALTERED. Try an AI-generated
   image for UNVERIFIED.

> The camera needs a secure context. `http://127.0.0.1` counts as secure, so
> **if this machine has its own webcam, `python run.py` already works with no
> extra setup at all.** The section below is only needed to test from a
> *separate* device — a phone.

### Testing with a real phone camera

`127.0.0.1` only works from the *same machine*. To point an actual phone's
camera at Veridact over your Wi-Fi, the connection needs HTTPS — one command,
no environment variables, works the same in PowerShell/Git Bash/cmd.exe:

```bash
pip install -r requirements.txt      # now includes pyOpenSSL
python run_phone_test.py
```

The startup banner prints every address Veridact is now listening on — open
the one that's your machine's actual Wi-Fi/LAN address (not a VPN adapter's)
on your phone's browser. It'll warn the certificate isn't trusted (expected —
it's self-signed and freshly generated); accept and continue, and the camera
permission prompt will work correctly from there.

Once you've enrolled on your phone, the Authenticate page auto-fills your
handle and private key from that enrolment — no manual copy/paste needed to
go straight from enrolling to capturing.

### Install it as its own app (PWA)

Veridact is an installable [Progressive Web App](decisions/0006-progressive-web-app.md) —
on your phone, after opening it, use your browser's **"Add to Home Screen"**
(iOS Safari) or the install prompt/menu option (Android Chrome). It'll add a
proper Veridact icon to your home screen that opens full-screen, no browser
address bar, feeling like its own dedicated camera app rather than a website.

## Project layout

```
run.py                on switch             config.py   settings (env-driven)
run_phone_test.py     on switch, HTTPS + LAN preset for testing with a phone
schema.sql            devices + manifests   app/        the application, split by job
  app/crypto.py       Schnorr verification    app/manifests.py  enrol/attest/verify, algorithm dispatch
  app/crypto_ecdsa.py ECDSA P-256 verification app/db.py        database access
  app/web.py          pages                     app/api.py        JSON API
                                                app/__init__.py   app factory
static/device.js      browser-side Schnorr keygen + signing (the capture agent)
static/ecdsa.js       browser-side ECDSA P-256 keygen + signing (Web Crypto)
decisions/            why it's built this way (ADRs)
```

## Verified

Phase 1 was exercised end-to-end, including running the **real `device.js`
browser code** against a live server: enrol → sign → VERIFIED CAPTURE, a
one-byte change → ALTERED, an unknown file → UNVERIFIED, and a signature forged
with a different key → **rejected**.

**Decision 0004's ECDSA P-256 path was verified the same way**, including one
real interoperability detail the proof surfaced: Web Crypto emits a raw `r‖s`
signature, while Python's `cryptography` library expects ASN.1 DER — caught by
testing against genuine Web Crypto output (via Node), not assumed correct from
documentation. The real, unmodified `static/ecdsa.js` was then run against a
live server: enrol → sign → VERIFIED CAPTURE, a replayed challenge → rejected,
and a signature from an unenrolled key → rejected. Existing Schnorr-enrolled
devices continue to verify unchanged (the schema migration is additive).
