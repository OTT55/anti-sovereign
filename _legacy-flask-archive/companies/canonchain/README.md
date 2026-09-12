# Canonchain — Rights Registry

**Sovereign Stack company #4 · Category: Rights Registry**

Canonchain is a cryptographic rights registry. In a world where any file can be
copied infinitely and perfectly, Canonchain answers a narrower, provable
question: *who registered this exact set of bytes first?* It does this without a
central authority you have to trust — using SHA-256 fingerprints and a Merkle
tree whose root commits to the entire registry state.

## Why cryptographic hashing proves authorship

A SHA-256 hash is a 64-character fingerprint of a file. It is:

- **Deterministic** — the same bytes always produce the same hash.
- **Collision-resistant** — you cannot feasibly find two different files with the
  same hash, so a hash uniquely identifies content.
- **One-way** — the hash reveals nothing about the file, so registering a hash
  discloses no content.

Because of this, a hash + a trusted timestamp is a claim of the form *"I held
these exact bytes at this time."* Whoever registers first has the earliest such
claim. No central authority decides authorship — the math does.

## Merkle inclusion proofs (what makes this more than a database)

Every registered hash is a **leaf** in a Merkle tree. Pairs of hashes are hashed
together up to a single **root** — one 64-hex value that fingerprints the whole
registry. For any registration, Canonchain produces an **inclusion proof**: the
short list of sibling hashes needed to recompute the root from that one leaf.
Anyone can run the proof locally: fold the leaf with each sibling and check that
you arrive at the published root. If you do, the entry is genuinely part of the
registry — the server cannot fake it or silently drop it.

```
            root = H(H12 + H34)
           /                    \
      H12=H(h1+h2)          H34=H(h3+h4)
      /        \            /         \
    h1         h2         h3          h4   <- leaves (registered hashes)
```

## How to run locally

```bash
cd companies/canonchain
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
python run.py
```

Open <http://127.0.0.1:5101>. (Set `CANONCHAIN_PORT` to use a different port.)

1. **Register** — choose any file. Your browser computes its SHA-256 locally
   (the file never uploads) and submits only the hash. You get a Registry
   Certificate with the registry ID, timestamp, Merkle root, and inclusion proof.
2. **Verify** — paste any hash. If registered, Canonchain returns the record and
   re-checks the inclusion proof against the current root.

Registering the same file twice returns HTTP 409 with the original registration —
first claim wins.

## Stack

- Backend: Python Flask (app-factory + blueprints) + SQLite (`canonchain.db`,
  created on first run). Structured as a real app — see
  [`PRODUCTION-PLAN.md`](PRODUCTION-PLAN.md) and [`decisions/`](decisions/) for the
  rationale behind every choice.
- Records are signed (HMAC-SHA256) so tampering with a stored registration is
  detectable; the signing secret is read from the environment, never committed.
- Hashing: Web Crypto API (client-side SHA-256) + Python `hashlib` (Merkle tree)
- Frontend: hand-written HTML/CSS/JS, no frameworks

## Project layout

```
run.py            on switch            config.py   settings (env-driven)
schema.sql        database shape       app/        the application, split by job
  app/db.py       database access        app/registry.py  hashing + Merkle math
  app/signing.py  tamper-evident seal    app/web.py       human pages
  app/api.py      JSON API (the seam)    app/__init__.py  app factory
decisions/        why it's built this way (ADRs)
```
