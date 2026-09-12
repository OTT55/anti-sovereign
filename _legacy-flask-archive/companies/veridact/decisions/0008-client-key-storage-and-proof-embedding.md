# 0008 — Client-side key storage (IndexedDB, non-extractable) and embedding the proof code in the saved photo

**Date:** 2026-08-02
**Status:** Accepted

## 1. The problem

Two friction points in the capture flow, both UX-only — neither touches what's
actually being proven:

1. **Manual key handling, every single capture.** Enrolling generated a
   private key and showed it as text to copy; the Authenticate page then
   required pasting that same text into a textarea (plus retyping the device
   handle) before every capture. Decision 0005 §7 patched the worst of this by
   auto-filling both fields from `localStorage` after enrolling in the same
   browser — a real improvement, but the key still existed as a plain JS
   string, readable by anything with page access, exactly the gap decision
   0004 flagged and deferred: *"the key can be copied, logged, screenshotted,
   or leaked by anything with access to the page."*
2. **Two things to save, every capture.** A capture produced a photo (to save
   as a file) and a separate proof code (to copy as text) — the user had to
   keep both together and re-supply both later to verify.

## 2. Decision

### 2a. Keys move to IndexedDB; ECDSA keys become genuinely non-extractable

Enrolling and capturing now read/write a device's key through
`static/keystore.js`, an IndexedDB wrapper, instead of a text box or
`localStorage`. This is a storage change only — `crypto.py`, `crypto_ecdsa.py`,
`manifests.py`, the manifest message format, and the server's verification
logic are all untouched. What changes is *where the private key lives between
enrolling and capturing*, not what gets signed or how a signature is checked.

**ECDSA P-256** (the default scheme, decisions/0004) is generated with
`extractable: false` (`static/ecdsa.js`'s new `generateEcdsaDeviceKeyStored`).
IndexedDB's structured-clone algorithm can store a `CryptoKey` object
directly — including a non-extractable one — so the key material is never
serialized to a string at any point after generation. `crypto.subtle.sign()`
can still use a non-extractable key to sign; it just can never be exported
back out, by this page's own JavaScript or anyone else's. This is exactly the
"stronger production direction" decision 0004 named and deferred — this pass
implements it.

**Schnorr** (the legacy/fallback scheme) is hand-rolled `BigInt` arithmetic,
not a Web Crypto key object — there is no non-extractable form available for
it at all. Its private scalar is still stored in IndexedDB (removing the
copy/paste step), and the enrolment UI still offers a collapsed "reveal for
backup" option, honestly labelled as not carrying the same protection ECDSA
gets. Stated plainly, not glossed over: **only the ECDSA path gets a real
security improvement here; the Schnorr path only gets a UX improvement.**

### 2b. A one-time import bridge for anything already enrolled

Devices enrolled before this change have a public key permanently on the
server (decisions/0002) but their private key only ever existed as text the
user was told to save. Rather than orphan them, the Enrol page has a
collapsed "import a saved key" form: paste it once, it's imported into
IndexedDB (via `importKey(..., extractable: false, ...)` for ECDSA — the
browser-side copy becomes non-extractable from that point forward, though
this obviously can't retroactively secure whatever plaintext copy the user
already saved elsewhere the first time). This is the only place a key is
still typed in; it is a one-time bridge, not the normal flow.

### 2c. The proof code travels inside the photo, not alongside it

`static/pngtext.js` embeds the manifest ID as a standard PNG `tEXt` metadata
chunk (30-year-old PNG spec — keyword + NUL + text, wrapped in the ordinary
length/type/CRC32 chunk framing) directly into the saved capture, right after
the mandatory `IHDR` chunk. The Verify page's file picker reads it back
automatically and pre-fills the manifest ID field (still editable) — the
common case now needs one file, not a file plus a code to separately copy.
The proof code is still shown and copyable in the capture result, as a
fallback for when metadata doesn't survive (see 2d.4 below).

### 2d. A bug this surfaced and fixed before shipping: hash the bytes that were actually signed

Embedding the code into the PNG **changes the file's bytes** — obviously, or
there'd be nowhere to put the code. That means the saved-with-embedded-code
file's hash never equals the hash that was signed, which would make *every
single untouched capture* verify as **ALTERED against itself** — exactly the
false alarm this project exists to avoid, and a much worse version of it than
an occasional real recompression, since it would fire 100% of the time. Caught
in testing, not shipped: `vdStripPngText` (the exact inverse of the embed —
same chunk removed byte-for-byte, not a re-encode) runs before hashing on the
Verify page whenever our chunk is present, recovering the exact bytes that
were originally signed. Verified end-to-end, not assumed: enrolled a real
non-extractable ECDSA device, captured, embedded, then confirmed the stripped
hash matches the pre-embedding hash exactly and the saved file resolves to
**VERIFIED CAPTURE** — and, separately, that a genuinely different file
(real tampering, not just our own metadata) still correctly resolves to
**ALTERED**. Both the Schnorr and ECDSA signing paths were exercised this way
against the running server, plus the enrol page's non-extractable-key path
(confirmed `cryptoKey.extractable === false` on the stored object itself, not
just assumed from the generation call).

## 3. Why this is the right cut

- **The whole point of a private key is that only the device holds it.**
  A key sitting in a JS variable (or `localStorage`) after every enrolment
  is a bigger practical risk than the cryptography itself — decision 0004
  said as much. Non-extractable storage closes that gap for the scheme that
  can support it, without waiting on hardware (the actual V2/V3 endgame,
  decisions/0001/0003).
- **Friction is a real adoption cost, not a cosmetic one.** A tool that asks
  for a pasted private key before every capture will get used carelessly
  (copied into notes apps, screenshotted, reused) purely to avoid the
  friction — which recreates the exact exposure the crypto is supposed to
  prevent. Removing the friction is a security improvement, not just a
  convenience one.
- **One file beats a file-plus-a-code for how people actually behave.** Real
  users forget to keep a text code paired with a photo; a self-contained file
  can't be separated from its own proof code by accident.

## 4. Trade-offs, stated honestly

- **A non-extractable ECDSA key can never be backed up, exported, or moved.**
  This is the direct cost of the protection: if the user clears this
  browser's site data, reinstalls, or switches browsers/devices, that
  device's key is gone for good — there is no recovery, by design. They
  would enrol again as a new device. This is a real, sharp trade-off, not a
  hidden one; the enrolment UI states it plainly at the moment of enrolling,
  not buried in this document.
- **IndexedDB is still same-origin JS-readable storage, not a secure
  enclave.** A non-extractable key can't be *exfiltrated* by another script
  on the page, but a malicious script could still *use* it to sign arbitrary
  manifests while it's present, same as before. This raises the bar (can't
  steal the key and use it elsewhere) but does not reach hardware attestation
  — still the documented next step (decisions/0001, 0003, 0004's WebAuthn
  discussion), not something this pass claims to solve.
- **Schnorr gets convenience, not protection.** Stated in §2a and in the
  enrolment UI itself — don't let the shared "stored, not pasted" framing
  imply a security property that only the ECDSA path actually has.
- **PNG metadata is not robust to recompression.** Sending the photo through
  WhatsApp, Messenger, or most social platforms strips PNG metadata (and
  usually re-encodes to JPEG entirely) same as it strips EXIF or C2PA. The
  embedded code is a convenience for the direct-file case, not a durability
  claim — closing that gap for real is the separate, larger watermarking
  question flagged for later work, not something this pass attempts.
