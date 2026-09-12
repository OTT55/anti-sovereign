# 0003 — App structure (why not one big file)

**Date:** 2026-07-21
**Status:** Accepted

## Context

The MVP was a single `app.py`. That's perfect for a demo and awful for a product:
everything is tangled together, so it's hard to test one part in isolation and easy
to break something far away when you change one thing.

## Decision

Split Canonchain into small parts, each with one job:

```
companies/canonchain/
  run.py            → the "on switch": starts the app
  config.py         → settings (file paths, secret, debug) — read from the
                      environment so nothing sensitive is hard-coded
  schema.sql        → the database shape (ADR 0002)
  app/
    __init__.py     → the "factory": assembles the app and wires the parts together
    util.py         → tiny shared helpers (timestamps, id generation)
    db.py           → talks to the database (the ONE place that does)
    signing.py      → the "wax seal": HMAC signing + checking
    registry.py     → the registry brain: hashing math + Merkle proofs (no web code)
    web.py          → the pages a human sees (/, /verify)
    api.py          → the JSON a machine sees (/register, /api/verify)
  templates/ static/ → the front-end (unchanged this phase)
```

## Why (plain English)

- **One job per file** means you can read `registry.py` and understand the Merkle
  math without wading through web code, and you can test it on its own.
- **The "app factory" pattern** (`create_app()`) is the standard professional way
  to build a Flask app. Its practical payoff: we can start a *fresh, isolated* copy
  of the app for automated tests (Phase 4) without it touching the real database.
- **Database access lives in exactly one file** (`db.py`). That's the seam that
  makes the future SQLite→PostgreSQL swap (ADR 0002) a small change instead of a
  hunt-and-replace across the whole app.
- **Pages and API are separate** (`web.py` vs `api.py`). The API is how other
  Sovereign Stack companies will talk to Canonchain later — building it as its own
  clean surface now means integration is "point at these endpoints," not a rewrite.
- **Nothing sensitive is hard-coded.** The signing secret comes from an environment
  variable (or a local, gitignored file), so the source code is safe to make public.

## Trade-off

More files than one `app.py`. For a throwaway script that would be overkill; for
the first real product in the Stack it's the difference between something you grow
and something you'd have to rewrite. The parts are small and named for what they
do, so the extra structure makes the code *easier* to follow, not harder.
