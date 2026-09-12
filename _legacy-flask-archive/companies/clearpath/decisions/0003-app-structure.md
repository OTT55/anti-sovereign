# 0003 — App structure (why not one big file)

**Date:** 2026-08-01
**Status:** Accepted

## Context

The MVP was a single `app.py` (251 lines) — fine for a demo, and already
getting crowded now that rules are data, reference data is versioned, facts
are tri-state, and every decision pins a frozen ruleset. Adding all of that
to one file would make the one part everyone actually needs to read (the
compliance logic) hard to find.

## Decision

Split Clearpath the same way Canonchain already did:

```
companies/clearpath/
  run.py              -> the "on switch"
  config.py           -> settings, read from the environment
  schema.sql           -> the database shape (0002)
  rulepacks/core.json  -> the rules, as data (0002)
  refdata/jurisdictions.json -> reference sets, as data (0002)
  app/
    __init__.py       -> the factory: assembles the app, wires blueprints
    util.py           -> timestamps, case-id generation
    conditions.py     -> the condition DSL — pure, no Flask/DB import (0002, 0004)
    rules.py          -> loads a rulepack, evaluate(facts, ruleset) -> decision
    audit.py          -> the hash chain: append + verify
    db.py             -> the ONE place that talks to the database
    web.py            -> pages a human sees (/, /audit, /__whoami)
    api.py            -> JSON a machine sees (/evaluate, /api/audit/*)
  templates/ static/  -> the front-end
```

## Why (plain English)

- **`conditions.py` has zero imports from the rest of the app.** It can be
  tested with plain dicts — no Flask app, no database — which matters more
  here than in most of this repo, because it's the piece that decides
  BLOCK/REVIEW/ALLOW/INSUFFICIENT_FACTS and needs to be trusted in
  isolation.
- **`rules.py` is also DB-free.** `evaluate(facts, ruleset)` is a pure
  function: same inputs, same output, forever. That purity is what makes a
  past decision replayable — the database only has to store *which* ruleset
  was used, not re-derive the answer some other way.
- **Database access lives in exactly one file** (`db.py`), same seam
  Canonchain uses, for the same future SQLite → PostgreSQL reason.
- **Pages and API are separate** (`web.py` vs `api.py`), same reason as
  Canonchain: the API is the surface other Sovereign Stack companies call
  later (Phase 2 is Canonchain calling *into* this surface's provenance
  logic, and this surface calling *out* to Canonchain).

## Trade-off

More files than one `app.py` — the same trade-off Canonchain's 0003 already
accepted, for the same reason: worthwhile the moment a company stops being a
demo and starts being something people build on.
