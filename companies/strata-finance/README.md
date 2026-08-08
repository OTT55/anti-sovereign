# Strata Finance — Capital Settlement

**Sovereign Stack company #6 · Category: Capital Settlement**

Strata Finance settles capital through **revenue waterfalls**. Money from a film
or IP deal rarely splits evenly — a distribution fee comes off the top, investors
recoup their principal, and only the remaining "backend" splits among the
participants. Strata lets you define that waterfall as ordered tiers and then
settle real payments through it, producing a double-entry ledger where the gross
received always equals the sum distributed.

## The waterfall model

A deal is an ordered list of tiers. Each incoming payment flows top to bottom:

| Tier | Behaviour |
|------|-----------|
| **Fee** | Takes a fixed percentage of the gross, off the top (e.g. 15% distribution fee). |
| **Recoupment** | Pays a party until a cap is reached. Caps are **stateful** — they deplete across settlements, so an investor recoups exactly their principal over time, no more. |
| **Split** | Distributes whatever remains among participants by percentages that must sum to 100%. |

## Correctness

- **Integer cents.** All arithmetic runs in whole cents, so there is no
  floating-point drift. In split tiers the last participant absorbs any rounding
  remainder, so distributions reconcile to the penny.
- **Double-entry invariant.** Every settlement asserts
  `sum(distributions) + holdback == gross`. If it ever failed, the settlement
  would not be recorded.
- **Stateful recoupment.** Amounts already paid to each recoupment tier are summed
  from the ledger, so re-running the waterfall on a later payment respects how
  much has already been recouped.

## How to run locally

```bash
cd companies/strata-finance
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5106>.

1. **Structure a deal** — add participants, then build the waterfall (or click
   **Load example** for a 15% distribution fee → $250k investor recoupment →
   40/60 backend split).
2. Open the deal and **settle a payment**. Watch the recoupment bar fill across
   multiple settlements and the ledger reconcile each gross amount in full.

## Stack

- Backend: Python Flask + SQLite; waterfall engine in pure integer arithmetic
- Frontend: hand-written HTML/CSS/JS with a dynamic waterfall builder, no frameworks
