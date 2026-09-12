# Sovereign Edit — Certification

**Sovereign Stack company #5 · Category: Certification**

A finished film ends up as a dozen near-identical files — `final.mov`,
`final_v2.mov`, `final_v3_REAL.mov` — spread across drives, festival portals, and
collaborators' inboxes. Six months later, nobody can reliably say which one is the
approved master.

Sovereign Edit records a film's production lineage as a chain nobody can quietly
rewrite, and answers the question that actually matters:

> **You're holding a file. What is it?**

## What it does

**Log the lineage.** Register a work, then log each production step as it
happens — capture, edit, colour grade, sound, VFX, master, release — with who did
it, what tool they used, and the file it produced.

**Chain it.** Each step is a block committing to the hash of the block before it:

```
block_hash = SHA-256(prev_hash + step fields)

Registration → Capture → Edit → Colour Grade → Master
   block0    →  block1  → block2 →  block3   → block4 → lineage hash
```

Alter any past step and its hash changes, breaking every link after it. Sovereign
Edit tells you **exactly which step** the lineage stops being trustworthy at — not
just a bare pass/fail.

**Identify any file.** Drop a file into **Identify** and get one of four answers:

| Verdict | Meaning |
|---|---|
| **APPROVED MASTER** | This is the cut that was signed off. Safe to send. |
| **NOT THE MASTER** | Part of the production, but an earlier stage — and it tells you which step *is* the master. |
| **IN LINEAGE** | Part of the production, but no master designated yet. |
| **NOT IN THE ARCHIVE** | Never seen. Not a recorded step of any tracked work. |

**Your footage never uploads.** Files are fingerprinted (SHA-256) in your browser.
Masters are tens of gigabytes; we only ever need the hash.

## How to run locally

```bash
cd companies/sovereign-edit
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
python run.py
```

Open <http://127.0.0.1:5105>. (Set `SOVEREIGN_EDIT_PORT` to use a different port;
see [PORTS.md](../../PORTS.md).)

1. **Register a work** — title + director.
2. **Log steps** — attach the file each step produced; it's hashed locally.
3. **Mark the approved master** on the step that is the signed-off cut.
4. **Identify a file** — drop the master back in to get APPROVED MASTER; drop an
   earlier cut in to get NOT THE MASTER; drop anything else in for NOT IN THE
   ARCHIVE.

## Honest scope

Sovereign Edit proves a file's **place in a recorded history**, and that the
history hasn't been altered since it was written. It does **not** prove the
history was true when written — log a step that never happened and the chain
faithfully records it. Tying steps to signed identities is the next step. See
[decisions/](decisions/).

## Project layout

```
run.py            on switch          config.py   settings (env-driven)
schema.sql        database shape     app/        the application, split by job
  app/db.py       database access      app/chain.py  hash-chain math (pure)
  app/works.py    domain rules         app/web.py    human pages
  app/api.py      JSON API             app/__init__.py  app factory
decisions/        why it's built this way (ADRs)
```

## Stack

- Backend: Python Flask (app-factory + blueprints) + SQLite
- Hashing: Web Crypto API (client-side) + Python `hashlib` (chain)
- Frontend: hand-written HTML/CSS/JS, no frameworks
