# Sovereign Stack — Company MVPs

A runnable basic MVP for each Sovereign Stack company. Every app is
self-contained: **Python Flask + SQLite + hand-written HTML/CSS/JS**, a dark
aesthetic with its own accent color, and **real cryptography from the standard
library** — nothing is mocked.

| # | Company | Category | MVP | Port |
|---|---------|----------|-----|------|
| 1 | [Veridact](veridact/) | Truth Infrastructure | **Capture attestation — prove a video is a real camera capture, not AI** (production app) | 5102 |
| 2 | [Nullform](nullform/) | Identity Layer | Zero-knowledge Schnorr proof of identity (key never leaves the browser) | 5103 |
| 3 | [Clearpath](clearpath/) | Compliance Routing | Jurisdiction rules engine → ALLOW/REVIEW/BLOCK + hash-chained audit log | 5104 |
| 4 | [Canonchain](canonchain/) | Rights Registry | SHA-256 registry + Merkle inclusion proofs + certificate | 5101 |
| 5 | [Sovereign Edit](sovereign-edit/) | Certification | Hash-linked film provenance chain + certificate of authenticity | 5105 |
| 6 | [Strata Finance](strata-finance/) | Capital Settlement | Revenue-waterfall settlement in integer cents + double-entry ledger | 5106 |
| 8 | [ContextCore](contextcore/) | Data Refineries | Local TF-IDF RAG over documents and **named collections** (persistent, growable, multi-document corpora) with cited answers. The `distribution-intelligence` collection is a structured release-strategy query mode over real case-study documents — same retrieval engine, no separate rules engine. | 5107 |
| 9 | [ArcVault](arcvault/) | IP Arbitrage | Genre-adaptation of public-domain works via Claude | 5108 |
| 11 | [Story Atlas](story-atlas/) | Creative Intelligence | **Structured workspace for building fictional universes — character DB, timeline, relationship graph, AI assistant, and a real Canon Engine consistency auditor** | 5109 |
| 12 | [Cinematic AI](cinematic-ai/) | Reference-Based Grading | (separate build, in progress) | — |

> Companies #7 (Epsilon Stack / creator OS) is intentionally not built here.

## Run them all

```bash
pip install Flask
python companies/run_all.py
```

Then open the printed `http://127.0.0.1:50xx` URLs.

## Run one

```bash
cd companies/<name>
pip install -r requirements.txt
python app.py
```

## Notes

- **ContextCore** and **ArcVault** make real Claude API calls for their
  *generative* step and need `pip install anthropic` + an `ANTHROPIC_API_KEY`.
  Without credit they surface the API error honestly (ContextCore still returns
  cited extractive answers; nothing is faked).
- Each app writes its own SQLite file on first run (gitignored).
- **Distribution Intelligence was a standalone company (LaunchWindow) and has
  been merged into ContextCore.** A release-strategy rules engine over a
  hand-curated dataset was functionally the same thing as RAG over real
  documents — retrieve relevant evidence, generate a cited answer — just with
  the "documents" as Python dicts instead of ingested text. ContextCore now
  supports **collections**: named, persistent, growable corpora spanning many
  documents (`/collection/<category>`), queried with the exact same retrieval
  engine as a single document. `distribution-intelligence` is the first
  collection, seeded via `contextcore/seed_distribution.py` with six original
  case-study documents; its structured form only builds a natural-language
  question — see `contextcore/README.md` for the full writeup.
