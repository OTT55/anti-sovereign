# RightsForge Engine

The domain authority for **ownership**, sitting on top of CreativeOS.

```bash
python demo.py
python -m pytest -q     # 66 tests
```

CreativeOS understands that two records are related. RightsForge understands
that an exclusive UK film licence and an exclusive worldwide film licence
**cannot both be sold**, and that an option which lapsed in March stopped being
anybody's in March.

## The one rule

> Two grants **collide** when their scopes overlap **and** their terms overlap
> **and** at least one of them is exclusive.

Everything in `rights.py` is that sentence, evaluated. Non-exclusive licences
never collide with each other — which is exactly why an asset sells a thousand
times and a film option does not sell twice.

## What a grant is made of

| | |
|---|---|
| **Scope** | which right, which territory, which medium. Film-in-the-UK and stage-in-the-UK can go to different buyers on the same day |
| **Term** | a start and an end. An option is time-limited *by definition*; a purchase is perpetual |
| **Exclusivity** | whether granting it forbids granting anything overlapping |

Collapse any of the three and the ledger starts lying.

## The gap this closes

The app models a listing with a single status column — `listed | optioned |
sold`. That column has no room for *until when*, so:

```
option agreed  ->  status = "optioned"  ->  the work is locked forever
```

Nothing can record that the rights came back. There is no expiry, no lapse, no
reversion — `expire`, `lapse`, `revert` and `term` appear **zero times** in
`companies/creativeos/rightsforge/app.py`.

Here, availability is **computed from the ledger at a moment**, never stored:

```python
forge.availability(script.id, "purchase", when=2030)   # blocked by the option
forge.availability(script.id, "purchase", when=2039)   # option lapsed; free
```

An option lapsing needs no cron job and no cleanup. The date passes and the
grant stops being live.

The engine also refuses to *create* a perpetual option at all — an option that
never lapses is an assignment with a smaller price tag.

## Money that adds up

`money.py` exists because this is the one place where being approximately
correct means somebody is short-changed.

- **Integer pence, never floats.** `0.1 + 0.2 != 0.3`, and a royalty ledger
  summed a few thousand times drifts far enough to show up in a payout.
- **The parts reconstruct the total, exactly.** 70/30 of £10.01 is 700.7p and
  300.3p; rounding each independently gives back 1001p only by luck. The split
  uses **largest remainder** — floor everything, then hand the leftover pence to
  whoever lost the most — which never invents or loses a penny.

A test asserts that property across every split against every amount from 0 to
£20, not against a hand-picked example.

**The app never validates that a split sums to 100%.** A 97% split is accepted,
which silently decides that somebody absorbs the missing 3%. Here it is refused
at listing time, not discovered at payout.

## Deal flow

```
asset :  paid                          (paying is the deal)
ip    :  proposed -> agreed -> paid    (one step at a time, forward only)
```

A deal that can jump to `paid` can skip agreement; a deal that can go backwards
can un-pay somebody. Neither is representable.

**Availability is checked when the deal opens, not at payment.** Letting a buyer
negotiate for weeks against a work somebody else already holds exclusively is
the expensive kind of wrong.

Reaching `paid` writes a **grant** into the ledger — with a scope and a term —
and only then publishes `ip.optioned` / `ip.licensed` / `ip.purchased` /
`asset.licensed`. The order is load-bearing and tested: a listener that reacts
by asking the ledger who holds the work must not arrive before the answer
exists.

## A tier is not a right

An asset's `personal` / `commercial` / `studio` tiers are **price bands**. Every
one grants the same non-exclusive licence; what the buyer may *do* with it is
the application's business rules, not something a rights ledger can enforce.

Feeding a tier name into the ledger as a deal kind was the first thing the tests
caught, and it was the right thing to catch — it would have meant inventing a
new kind of right every time somebody named a new pricing tier.

## Boundaries

Publishes events and holds **no reference to FrameVault** or any other
application, exactly like FilmCrew. A test parses the engine's *imports* (not
its text — the docstrings mention siblings while explaining the boundary) and
fails if it ever reaches sideways.

The term-overlap arithmetic is the same as StoryAtlas's lifespan reconciliation
and is deliberately **not** imported from it. Applications depend on the
platform beneath them, never on each other. If it needs sharing it belongs in
CreativeOS, not in a sibling.

## Honest limitations

- **Scope has three axes** (right, territory, medium). Language, window and
  holdback are real axes in a distribution deal and are not modelled. The
  overlap test does not care how many there are, so adding one is mechanical.
- **Time is a plain comparable** — the tests use years. Real terms are dates;
  the engine never does arithmetic on them beyond `<`, so a `date` works
  unchanged, but nothing here parses one.
- **No payment execution.** It computes who is owed what; moving money is not
  the engine's business.
- **The ledger is in-memory.** Persistence is the application's job.
