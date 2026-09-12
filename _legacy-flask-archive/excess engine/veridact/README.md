# Veridact Engine

Proving a capture — **not** detecting a fake.

```bash
python demo.py
python -m pytest -q      # 19 tests, real ECDSA P-256 keys
```

## The decision the product rests on

Veridact does not analyse pixels to guess whether media was generated. That is
an arms race between detectors and generators which detectors lose, and it gets
harder every year. The app's ADR 0001 ruled it out and this engine follows.

Instead it verifies a **capture attestation**: a device signs the media at the
moment of capture with a private key Veridact never sees. Veridact holds only
the public key — so it can check a signature and is **structurally incapable of
forging one.** An operator who cannot forge cannot be pressured into forging,
and a breach leaks nothing that lets anyone else either.

## Three properties, three attacks

| The signature covers | Defeats |
|---|---|
| the **media hash** | tampering — edit one byte and nothing vouches for it |
| a **server-issued nonce** | replay — otherwise one signature works on any file, forever |
| the **capture time** | re-attesting old footage as if it were new |

And the nonce is single-use and expires in 120 seconds, so a stolen one cannot
be hoarded.

## Three verdicts, never four

```
VERIFIED_CAPTURE   signed by an enrolled device, unchanged since
ALTERED            a capture was attested, but the signature no longer matches
UNVERIFIED         no attestation exists, or it can no longer be checked
```

**There is no `FAKE`.** Not as a policy — the value does not exist to be
returned, and a test asserts its absence. Absence of proof is not proof of
absence, and most honest media in the world has never been attested at all.
A product that blurs those two is lying about what it knows.

The distinction between `ALTERED` and `UNVERIFIED` is deliberate and load-bearing:

- *"We have never seen this"* is **not an accusation**.
- *"We have seen this and it no longer matches what was signed"* is a claim
  about the file.

Collapsing them into one negative answer throws away the only distinction that
matters to someone being accused.

## Why revocation degrades to UNVERIFIED

Revoking a device keeps its manifests. Verification then returns `UNVERIFIED`,
not `ALTERED` — the claim still exists, it just cannot be checked any more.
Marking it `ALTERED` would accuse a file of something it did not do, on the
strength of an administrative action it had no part in.

## Structure

```
src/veridact_engine/
  attestation.py   hashing, the signing message, verdicts, signature backends
  registry.py      enrolment, challenges, attestation, verification
tests/             19 tests against real P-256 keys
demo.py            enrol → capture → verify → tamper → replay → revoke
```

Signature schemes are an **interface**, not a hard-coded choice, because a
manifest records which algorithm signed it. Pinning one into the verifier would
silently orphan every manifest signed under another — the app already supports
two, and its default has changed once.

## Honest limitations

- **Attestation proves capture, not truth.** A device can faithfully sign a
  photograph of a screen showing something generated. Veridact proves *this
  device captured these bytes at this time*, which is a narrower and more
  defensible claim than "this is real".
- **A compromised device compromises its captures.** If a private key is
  extracted, anything signed with it verifies. Hardware-backed keys are the
  answer and are the app's documented next step.
- **The registry is in-memory.** Persistence is the application's job; this is
  the engine.
- **`HMACSigner` is for tests only** and says so — symmetric signing means the
  verifier could forge, which is the exact property Veridact exists to avoid.
  `is_asymmetric` is `False` so nothing mistakes it for production-grade.
