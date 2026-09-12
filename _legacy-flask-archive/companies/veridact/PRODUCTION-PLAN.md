# Veridact — Production Build Plan (plain English)

Written for OTT (founder / CEO / CTO). You should be able to read this, weigh each
call yourself, and explain it to a university or investor. No jargon without a
plain-English translation beside it.

This is the plan to take Veridact from the **MVP** (already built) to a **real
production-grade application** — the first one in the Sovereign Stack. It replaces
Canonchain as our first build, because Canonchain (a rights registry) overlaps with
FrameVault, which is being built separately. Veridact does something FrameVault does
**not**: it answers *"is this video real, or AI?"*

---

## 1. What Veridact is, in one breath

Veridact proves a video (or photo) is a **real, unaltered capture from a genuine
device** — not an AI generation, and not edited after the fact. It's the *Truth
Infrastructure* of the Sovereign Stack: when AI content is infinite, the scarce,
valuable thing is **verified real origin.**

---

## 2. The core idea — and why we do it this way (READ THIS)

There are two ways to "prove a video is real, not AI." Only one actually works.

1. **❌ Analyse the pixels and guess** ("AI detectors"). This is an arms race —
   every detector is beaten by the next AI model. It can never *prove* anything,
   only guess, and it gets worse over time. **We do not build this.**

2. **✅ Prove where the video came from (capture attestation).** At the moment of
   recording, the capturing device **cryptographically signs** the footage. Later,
   anyone can check that signature and confirm: *this came from a genuine, enrolled
   capture device and has not been changed since.* You're not detecting AI — you're
   proving real origin, which is **certain**, not a guess. This is also how the
   industry standard "Content Credentials / C2PA" works.

**The verdict Veridact returns is one of three — and this honesty is the product:**

| Verdict | Meaning |
|---|---|
| **VERIFIED CAPTURE** | Signed by an enrolled device and unaltered since capture — real. |
| **ALTERED** | Was captured by a known device, but the file changed afterwards (edited, re-encoded, or AI-processed). |
| **UNVERIFIED** | No valid capture signature. Could be AI-generated, or simply from a device that doesn't sign. We make **no claim** — absence of proof is not proof of fakery, and we say so. |

That third row is the intellectually honest core: Veridact proves *real*, it never
pretends to prove *fake*.

---

## 3. What we can honestly build in V1 (and its honest limit)

**The gold standard** is a secure chip *inside the camera* holding the signing key,
so the key can never be copied. That needs hardware cooperation we don't control
yet — it's the documented V2/V3 upgrade.

**What V1 builds — real, working, no special hardware:** a **software capture
agent**.

1. **Enrol a device/creator.** The agent generates a keypair; Veridact stores only
   the **public** key. The private key stays on the device — Veridact can *check*
   signatures but can never *forge* them.
2. **Sign at capture.** When a video is recorded or imported through the agent, it
   hashes the media + capture details (time, device id) and **signs** that with the
   device's private key, producing a **capture manifest** (a signed provenance
   record) that travels with the file.
3. **Verify.** Anyone submits the file (or its hash) + manifest. Veridact re-hashes
   it, checks the hash matches (unaltered) and the signature verifies against the
   enrolled public key (genuine device) → returns one of the three verdicts above.

**The honest limit, stated up front:** in V1 the key lives in software, so this
proves *"signed by an enrolled capture agent, unaltered since"* — a software-level
attestation. Moving the key into camera hardware (a secure enclave / TEE) is the
next step and is what makes it unforgeable even by the device's owner. V1 is the
real protocol; V2 hardens where the key lives. Nothing in V1 is throwaway.

---

## 4. What's different from the Veridact MVP

The MVP signed manifests with **HMAC** — a shared secret held by the *server*. That
proves "this server issued this record," which is fine for tamper-detection but
**can't prove which device captured something**, because the server holds the key
and could sign anything itself.

Production upgrades to **asymmetric signatures** (a private key that signs, a
separate public key that verifies). Now the **device** signs and the **server only
verifies** — the server cannot forge a capture. This is the single most important
upgrade, and it's exactly the "why this crypto and not that" decision recorded in
`decisions/0002`.

---

## 5. The build, in phases

- **Phase 1 — Foundation.** Real app structure; device/creator enrollment (public
  keys); asymmetric-signature manifests replacing HMAC. Verify keeps working.
- **Phase 2 — Capture & Verify.** In-browser capture agent (record/import → hash →
  sign with the device key, in the browser); the three-verdict verifier with clear
  reasons.
- **Phase 3 — Product & Proof.** Clean record/verify UI; automated tests; run it
  end-to-end for real; write the "how this hardens to hardware attestation + scales"
  doc.

Each phase ends with a working app and a git commit.

---

## 6. Decisions that are yours

1. **Signature scheme** (see `decisions/0002`): my recommendation is **Ed25519**,
   the modern industry-standard signature — *if* we can add the small `cryptography`
   library. If you'd rather keep **zero external dependencies**, we reuse the
   Schnorr signature scheme already proven in this repo (Nullform). Both are real
   asymmetric crypto; I'll recommend one when we get there.
2. **V1 scope**: are you happy with **software** capture attestation for V1, with
   hardware-backed keys as the documented next step? *(Recommended — it's the real
   protocol; hardware is a where-the-key-lives upgrade, not a redesign.)*

Nothing here locks us in. Push back on any of it and I'll adapt before building.
