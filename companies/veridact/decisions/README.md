# Decisions — why Veridact is built the way it is

This folder is Veridact's memory. Every meaningful choice gets a short, dated,
numbered file here called an **ADR** (*Architecture Decision Record*): what forced
the decision, what we chose, why, and the honest trade-off.

**Why we do this:** so the *why* is never lost. Months later — or in a university
interview, or when a collaborator joins — nobody has to guess. The reasoning is
written down and kept in git next to the code it explains. We don't delete old
decisions; if one changes, a new ADR supersedes it, preserving the history of
thinking.

## Index

- [0001 — Veridact is the first production app; the attestation approach](0001-scope-and-approach.md)
- [0002 — Signatures: why asymmetric keys, not the MVP's HMAC](0002-signatures.md)
- [0003 — Veridact captures; it does not accept uploads](0003-capture-not-upload.md)
- [0004 — Cryptographic primitive review: Schnorr vs. ECDSA P-256 vs. WebAuthn](0004-cryptographic-primitive-review.md)
- [0005 — Testing the capture agent with a real camera or phone](0005-real-camera-testing.md)
- [0006 — Veridact as an installable PWA, not (yet) a native app](0006-progressive-web-app.md)
- [0007 — Positioning: interoperate with C2PA, target an underserved niche](0007-positioning-interop-not-competition.md)
- [0008 — Client-side key storage (IndexedDB, non-extractable) and embedding the proof code in the saved photo](0008-client-key-storage-and-proof-embedding.md)
- [0009 — Soft-binding watermark: TrustMark, so recompression doesn't read as tampering](0009-soft-binding-watermark.md)
- [0010 — Writing real C2PA manifests at capture time, not just reading them](0010-c2pa-writing.md)
- [0011 — Fixing a real bug: the proof code was breaking C2PA validation](0011-embedding-order-fix.md)
