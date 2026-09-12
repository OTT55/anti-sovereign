# 0002 — Rules and reference data become versioned data, not code

**Date:** 2026-08-01
**Status:** Accepted

## Context

The MVP's six rules were Python functions (`rule_sanctions`, `rule_aml`, ...)
in `app.py`, and the sets they checked against — sanctioned countries,
GDPR-adequate destinations, data-localization jurisdictions — were hardcoded
Python literals (`SANCTIONED = {"IR", "KP"}`). Two concrete problems follow
from that:

1. Changing a rule (a threshold, a jurisdiction, wording of a citation) means
   editing Python and redeploying. A real compliance product needs someone
   who isn't a programmer to make that change, reviewably, without a deploy.
2. A literal like `SANCTIONED = {"IR", "KP"}` can go stale with nothing to
   notice it. Real sanctions lists change; the code gave no signal that this
   one hadn't been looked at since it was written.

## Decision

1. **Rules live in `rulepacks/*.json`** (starting with `core.json`, the six
   MVP rules ported faithfully). Each rule carries its outcome, legal basis,
   a citation URL, an `effective_from`/`review_by` date, and an owner —
   metadata the Python functions had no place to put.
2. **Reference data lives in `refdata/*.json`** (`jurisdictions.json`),
   versioned the same way and referenced by a rule pack
   (`"refdata": "jurisdictions@2026.1"`), so a rule pack always names exactly
   which snapshot of sanctioned/adequate/localization sets it was written
   against.
3. **A rule's condition is a small JSON tree** (`app/conditions.py`) —
   `{"and"|"or"|"not": [...]}` combinators over
   `{"field", "op", "value"|"ref"|"param"}` leaves — interpreted by a
   ~70-line hand-written evaluator, not a pip dependency. Two named
   conditions per rule: `applies_when` (is this transfer even the kind this
   rule is about — always answerable from hard facts) and `fires_when` (does
   it actually trigger, which may depend on facts the caller marked
   "Unknown" — see 0004).
4. **Every audit entry pins the exact `ruleset_id` that decided it.** The
   `rulesets` table stores the frozen rule + reference-data JSON verbatim, not
   just a hash, and a version is immutable once inserted — editing
   `core.json` without bumping its version fails loudly at boot
   (`app/db.py: _register_ruleset`) rather than silently reinterpreting past
   decisions.

## Why

- **A JSON diff is a real review artifact.** Changing the AML threshold from
  $10,000 to $15,000 is now a one-line change to `rulepacks/core.json`,
  reviewable in a pull request by someone who has never opened `app.py`.
- **This is not yet "a compliance officer edits rules in production."** That
  needs an admin UI, authentication, and an approval workflow — deliberately
  out of scope here (`PRODUCTION-PLAN.md` Phase 3). What this phase buys is
  the harder, load-bearing part: the rules already *are* data, so that UI is
  a future presentation layer over the same schema, not a rewrite of the
  engine.
- **Hand-rolled, not a library**, matching how this repo already hand-rolls
  Merkle trees (Canonchain) and Schnorr proofs (Nullform, Veridact) rather
  than reaching for a package to do something small and well-understood.
- **A frozen ruleset per decision is what makes "reproducible" true, not
  aspirational.** A decision made today against `core@2026.1` will replay
  identically in an audit eighteen months from now even after `core@2026.5`
  is live, because the entry doesn't point at "the rules" — it points at one
  immutable row.

## Trade-off

- The condition DSL is real infrastructure to learn — a new rule author
  writes a JSON tree instead of an `if` statement. Accepted because the
  entire point is that a rule change shouldn't require touching Python.
- `refdata/jurisdictions.json` is still hand-authored, not a live sanctions
  feed. It can still go stale — but now staleness is a dated, versioned file
  with a `review_by` field, not an invisible Python literal. Sourcing it from
  a real feed is future work, not solved here.
