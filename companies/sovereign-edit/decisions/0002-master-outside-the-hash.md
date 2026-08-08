# 0002 — The master designation sits outside the hash

**Date:** 2026-07-22
**Status:** Accepted

## Context

One step in a work is the **approved master** — the cut that was signed off. But
which cut that is legitimately changes: you re-grade, you fix audio, the festival
asks for a different aspect ratio, and the master moves.

That creates a conflict. The chain is supposed to be immutable. If `is_master`
were part of a block's signed fields, then changing your mind about the master
would rewrite a past block, break the chain, and make Sovereign Edit report
tampering — for a completely normal creative decision.

## Decision

**`is_master` is stored on the step but deliberately excluded from
`block_hash`.** The chain commits to *what happened* — who did what, when, to
which file. The master designation is a *current decision about* that history, and
it is allowed to change without breaking anything.

## Why

The two things are genuinely different kinds of fact:

| | Immutable (in the hash) | Mutable (outside it) |
|---|---|---|
| What it is | A record of an event | A decision about the record |
| Example | "On 3 May, J. Doe graded this file" | "The master is step #4" |
| Changing it means | history was rewritten → alarm | you changed your mind → fine |

Putting a mutable decision inside an immutable structure would produce constant
false alarms, and a tamper alert that cries wolf is worse than none — people learn
to ignore it.

## Trade-off

- **Master designation is not itself tamper-evident.** Someone with database
  access could silently switch which step is the master, and the chain wouldn't
  notice. That's a real gap, accepted because the alternative (false tamper alerts
  on every legitimate re-master) is worse.
- **The upgrade path is append-only:** record master changes as their own chained
  blocks (`Master designated: step #4`), so the *history of designations* becomes
  immutable while the *current* designation stays free to move. That's the right
  V2 and needs no schema change to the existing chain.
