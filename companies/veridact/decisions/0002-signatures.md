# 0002 — Signatures: why asymmetric keys, not the MVP's HMAC

**Date:** 2026-07-22
**Status:** Accepted — resolved to Schnorr (see "Resolution")

## Context

Veridact's whole promise is "this came from a genuine capture device." That promise
lives or dies on *who can produce a valid signature*. The MVP used the wrong tool
for this specific job, and fixing it is the most important upgrade in V1.

## The two kinds of "signature" (plain English)

**HMAC (what the MVP used) — a shared secret.** Imagine one secret password that
both the signer and the checker know. You can check a tag is genuine, but because
*you also hold the secret*, you could have made the tag yourself. Great for "did
this record get altered?" Useless for "which specific device made this?" — because
the server holds the key and could sign anything in a device's name.

**Asymmetric signatures — a private key that signs, a public key that checks.**
Two matched keys. The **private** key (kept on the device, never shared) makes
signatures. The **public** key (given to Veridact) only *checks* them. The checker
can verify a signature but **cannot forge one**. This is the only kind of signature
that can prove *origin*, because only the device could have signed.

## Decision

**Veridact uses asymmetric signatures.** The capture device signs with its private
key; Veridact stores and verifies with the public key. The private key never
reaches the server, so Veridact can prove a capture is genuine but can never fake
one. This is what turns "the server vouches for this" into "the *device* attests to
this."

## Why this matters concretely

If Veridact held the signing secret (HMAC), then a breach of Veridact — or a
dishonest insider — could mint "verified real" stamps for AI videos. With
asymmetric keys, there is nothing on Veridact's servers that can forge a capture.
The trust is anchored at the device, which is where "it's real" actually originates.

## Open call — which asymmetric scheme

Two real options; both are genuine public/private-key cryptography.

- **Ed25519 (recommended).** The modern industry-standard signature — fast, tiny,
  widely audited, and what real Content-Credentials systems use. Needs the small,
  standard `cryptography` Python library.
- **Schnorr over a 2048-bit group (zero-dependency fallback).** Already implemented
  and proven in this repo (Nullform). Uses only Python's standard library, so it
  adds nothing to install — at the cost of being our own code rather than an
  audited library.

Recommendation: **Ed25519** if we can add `cryptography`; otherwise reuse the repo's
Schnorr. Decided at the start of Phase 1 once we confirm the dependency installs.

## Resolution (2026-07-22)

At the start of Phase 1 we tried to install `cryptography`; it failed in this
environment (offline, broken package cache). Rather than block the build on a
dependency we can't fetch, **we use Schnorr signatures over the 2048-bit MODP group
(RFC 3526, group 14)** — the scheme already implemented and end-to-end verified in
this repo (Nullform). It is genuine asymmetric cryptography with the exact property
we need: the device signs with its private key `x`, Veridact verifies with the
public key `y = gˣ mod p`, and Veridact can never forge a signature. It also runs in
every browser (via `BigInt`) and adds **zero** dependencies.

**How a Schnorr signature works here:** to sign a manifest string `m`, the device
picks a random `r`, computes `t = gʳ mod p`, a challenge `c = H(g, y, t, m)`, and
`s = r + c·x (mod p−1)`. The signature is `(t, s)`. Veridact checks
`gˢ ≡ t · yᶜ (mod p)` — true only if the signer knew `x`.

**When we'd revisit:** if/when `cryptography` (or Web Crypto ECDSA P-256, which is
browser-native) is available in the deploy target, migrating is a swap of the
`crypto` module — the manifest format and the rest of the app don't change. Ed25519
/ ECDSA-P256 are more compact and library-audited; that's the upgrade. For now,
"works everywhere with no dependency, and is already proven here" wins.

## Trade-off

- Asymmetric signatures are a little heavier than HMAC and require key management
  (each device has its own keypair). That key management *is* the point — it's what
  ties a capture to a specific device.
- Choosing a library (Ed25519) means a dependency; choosing our own code (Schnorr)
  means owning the crypto. We prefer the audited library for something this
  security-critical, and keep the vetted fallback ready.
