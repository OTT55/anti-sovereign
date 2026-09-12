# 0001 — Clearpath is the next production app; scope & approach

**Date:** 2026-08-01
**Status:** Accepted

## Context

Canonchain, Veridact, and Sovereign Edit are already promoted to production
structure. `research/04-clearpath.md` (an earlier ground-truthing pass) named
three concrete gaps standing between the Clearpath MVP and something real:
rules need to be editable without a code deploy, the reference data
(sanctioned countries, GDPR-adequate destinations) is hardcoded and goes
stale silently, and the content-provenance rule trusts a caller-supplied
boolean instead of actually checking Canonchain or Veridact.

Separately, a moat analysis of the whole portfolio
(`research/14-business-moats-by-company.md`) found Clearpath sitting on the
strongest regulatory tailwind in the Stack: the EU AI Act's Article 50
transparency obligations apply from **2 August 2026**, converting AI-content
disclosure from a nice-to-have into a record-keeping obligation with a
per-violation fine attached. Clearpath is the only company positioned to
answer "prove you disclosed it" with a reproducible, tamper-evident decision
trail.

## Decision

1. **Clearpath is the next production app**, following the same path as
   Canonchain/Veridact/Sovereign Edit.
2. **We build in place**, evolving `companies/clearpath/`. The MVP
   (`app.py`, six rules, hash-chained audit log) is preserved in git history,
   not on disk — nothing is lost, the working tree just stops carrying it.
3. **This phase (Phase 1) stays fully offline** — no calls to Canonchain,
   Veridact, or any external service. It fixes the two gaps that don't
   require another company to be involved (rules-as-data, tri-state facts);
   wiring the provenance rule to a real Canonchain lookup is Phase 2,
   written up in `PRODUCTION-PLAN.md`.

## Why

- **The gaps were already diagnosed, not newly discovered.** Building
  exactly what `research/04-clearpath.md` called for means this phase has no
  open design question about *what* to build — only *how*.
- **Offline-first, same as Canonchain's own first phase.** A demo that needs
  another live service to work is a demo that can fail for reasons that have
  nothing to do with compliance logic. Phase 1 proves the harder, more
  foundational thing — rules as reproducible, versioned data — without that
  dependency.
- **The regulatory deadline is real and immediate**, which is why this was
  picked over the other unpromoted MVPs (Nullform, Strata Finance) despite
  all three being equally "ready" by structure alone.

## Trade-off

Same trade-off Canonchain's 0001 already accepted: SQLite has one writer, and
a single `rulepacks/core.json` is a toy-sized rule set next to what a real
multi-jurisdiction compliance product needs. Both are the right call until
there's a concrete reason (real load, a second rule pack) to revisit them —
see `PRODUCTION-PLAN.md` Phase 3.
