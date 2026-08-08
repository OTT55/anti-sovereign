# 0001 — Veridact is the first production app; the attestation approach

**Date:** 2026-07-22
**Status:** Accepted

## Context

We first chose Canonchain (a rights registry) as the first production app, then
realised it overlaps with FrameVault, which is being built on a separate track.
The founder's actual goal is different: **prove a video is a real camera capture,
not AI.** That is Veridact's job (Truth Infrastructure), so Veridact replaces
Canonchain as the first production build.

The hard part is *how* you prove "real, not AI" in a way that actually holds up.

## Decision

1. **Veridact is the first production app.**
2. **We prove real origin by capture attestation, not by AI-detection.** Veridact
   verifies a cryptographic signature made at capture time; it does **not** analyse
   pixels to guess whether content is AI.
3. **Veridact returns three verdicts** — VERIFIED CAPTURE, ALTERED, UNVERIFIED —
   and never claims to prove content is *fake*. Absence of a valid capture proof is
   reported as "unverified," not "AI."
4. **V1 is a software capture agent.** The device signs with a software-held key
   now; moving the key into camera hardware (a secure enclave) is the documented
   next step.

## Why

- **Pixel-based AI detection is unwinnable.** It's an arms race that every new
  generative model wins. A product built on it would make claims it can't keep. We
  refuse to ship a guess dressed as a proof.
- **Attestation is certain.** A valid signature from an enrolled device is
  mathematical proof of origin and integrity — not probabilistic. This is also the
  direction of the industry standard (C2PA / Content Credentials), so we're building
  toward interoperability, not a private island.
- **Three honest verdicts are the product.** The credibility of a truth-infrastructure
  company *is* its honesty. Saying "unverified — we make no claim" where a competitor
  would bluff "likely fake" is a feature, not a weakness.
- **Software V1 is the real protocol.** Everything except *where the key lives* is
  identical to the hardware version, so V1 is a foundation we harden, not a mock we
  replace.

## Trade-off

- **V1 can't stop a determined faker who extracts the software key** and signs a
  fake as if from a real device. That's exactly why hardware-backed keys are the
  next step. We state this limit openly rather than overselling V1.
- **Attestation only helps content that was signed at capture.** Most video in the
  wild isn't signed yet, so it lands in "unverified." That's honest, and it's the
  same bootstrap every provenance standard faces — value grows as more capture
  devices sign.
