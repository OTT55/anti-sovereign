# 0004 — Tri-state facts and a fourth outcome, INSUFFICIENT_FACTS

**Date:** 2026-08-01
**Status:** Accepted

## Context

The MVP built its three disclosure flags with `bool(data.get("contains_pii"))`
(and the same for `party_verified`, `provenance_attached`). That collapses two
different situations into one value: *the caller checked and the answer is
no*, and *the caller didn't say*. A caller who simply omits `party_verified`
gets silently treated as "definitely not verified."

For these three specific flags that happens to fail conservative — "unknown"
collapsing to "no" still triggers REVIEW rather than a false ALLOW. But that's
an accident of which direction these three rules happen to check, not a
property of the design. A future rule pack (tax withholding, labor
classification) will have flags where the safe default isn't so obviously
guessable, and a compliance engine that can't say "I don't know" will
eventually confidently clear something it was never actually able to judge.

## Decision

The three disclosure facts become **tri-state**: `true`, `false`, or `null`
("not yet known"). `app/conditions.py` propagates unknown using **Kleene's
three-valued logic**, not Python's two-valued `bool`:

- `AND` is `False` if any operand is `False` — regardless of others being
  unknown — else `None` if any operand is unknown, else `True`.
- `OR` is `True` if any operand is `True` — regardless of others being
  unknown — else `None` if any operand is unknown, else `False`.

A rule's `fires_when` resolving to `None` produces a new outcome,
**`INSUFFICIENT_FACTS`**, instead of silently resolving as if the missing
fact were `False`. Severity ranks it **above REVIEW, below BLOCK**: not
knowing something is worse than a known, resolvable REVIEW-level concern —
but a confirmed BLOCK (a sanctioned jurisdiction) still wins outright,
because knowing *one* thing is definitely prohibited doesn't become less true
because something unrelated is also unknown.

## Why (the case that forced three-valued logic specifically)

`data_localization` fires when `destination in LOCALIZATION AND
(contains_pii OR asset_type == "dataset")`. Two scenarios:

- `asset_type == "dataset"`, `contains_pii` unknown: the inner OR is `True`
  the moment one operand is `True` — Kleene logic doesn't need the other
  operand, so this correctly still fires REVIEW without needing to know
  `contains_pii` at all.
- `asset_type != "dataset"`, `contains_pii` unknown: the inner OR has no
  `True` operand and one unknown, so it resolves `None` — correctly
  `INSUFFICIENT_FACTS`, because the rule genuinely cannot be resolved from
  what's known.

A simpler design — "if any fact this rule touches is missing, short-circuit
to INSUFFICIENT_FACTS before evaluating" — was considered and rejected: it
gets the second case right and the first case *wrong*, flagging
`INSUFFICIENT_FACTS` even when the dataset branch alone already made the
rule fire, which would make the UI ask the user for information the decision
never actually needed. Real three-valued logic was the only way to get both
cases right with one mechanism instead of a special case per rule.

## Honest limit

This closes the *omission* hole: not stating a fact now reads as "unknown,"
not as a confident answer. It does **not** close a second, different hole
that already existed in the MVP and still exists here: `content_provenance`'s
`provenance_attached` flag is still whatever the caller asserts — Clearpath
does not yet call Canonchain or Veridact to check it independently. A caller
can still simply claim `provenance_attached: true` and be believed. Verifying
that claim against a real registry is Phase 2 (`PRODUCTION-PLAN.md`),
deliberately not solved in this phase.

## Trade-off

Three-valued logic is more than a rule author has to hold in their head
compared to a plain `if`. Justified because the alternative was tried in
design (a blunt "required fields" pre-check) and found to silently misfire
on the OR-short-circuit case above — getting this right needs the real
semantics, not a shortcut that's correct most of the time.
