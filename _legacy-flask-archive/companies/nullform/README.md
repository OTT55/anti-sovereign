# Nullform — Identity Layer

**Sovereign Stack company #2 · Category: Identity Layer**

Nullform proves *who you are* without revealing *what you know*. Passwords, API
keys, and secrets are all shared secrets — to prove you hold one you transmit it,
and now it can be intercepted, logged, or leaked. Nullform replaces the shared
secret with a **zero-knowledge proof of identity**: you prove you control a
private key without the key ever leaving your device.

## The primitive: a non-interactive Schnorr proof

Nullform works in a 2048-bit MODP group (RFC 3526, group 14) with generator
`g = 2` and prime `p`.

- **Enrolment.** Your browser generates a private key `x` and computes the public
  key `y = gˣ mod p`. Only `y` is sent to the server — `x` never leaves the page.
- **Proof.** To authenticate for a specific `message` (a login context, a
  transaction), your browser:
  1. picks a random nonce `r`, computes commitment `t = gʳ mod p`
  2. derives challenge `c = SHA-256(g, y, t, message)` (Fiat–Shamir)
  3. computes response `s = r + c·x  (mod p−1)`
  and sends only `(t, s)`.
- **Verification.** The server checks `gˢ ≡ t · yᶜ (mod p)`. This holds only if
  the prover knew `x`, but the equation leaks nothing about `x` — that is the
  zero-knowledge property. Because `c` includes the `message`, a proof is bound
  to its context and cannot be replayed elsewhere.

## Why this matters for an identity layer

- **No shared secret in transit.** The server stores only public keys. A breach
  of Nullform's database reveals no credentials.
- **Phishing-resistant.** There is nothing to type into a fake form — proofs are
  built locally and are message-bound.
- **Foundation for selective disclosure.** The same commitment machinery extends
  to proving *attributes* ("over 18", "accredited") without revealing the
  underlying data — the direction the full Nullform product takes.

## How to run locally

```bash
cd companies/nullform
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5103>.

1. **Enrol** — choose a handle. Your keypair is generated in-browser; save the
   private key shown (it is never stored server-side and cannot be recovered).
2. **Prove** — enter your handle, private key, and any challenge message. A valid
   proof returns **IDENTITY PROVEN**. Change one character of the private key or
   the message and it returns **PROOF REJECTED**.

## Stack

- Backend: Python Flask + SQLite, `pow()` big-integer modular arithmetic (stdlib)
- Frontend: hand-written HTML/CSS/JS using `BigInt` for client-side key generation
  and proof construction; Web Crypto API for the SHA-256 challenge
