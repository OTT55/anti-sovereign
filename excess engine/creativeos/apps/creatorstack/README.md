# CreatorStack Engine

The domain authority for **competitions**, sitting on top of CreativeOS.

```bash
python demo.py
python -m pytest -q     # 49 tests
```

CreativeOS understands connections. CreatorStack understands that a deadline is
a fact about time rather than a status somebody remembers to flip, that a
creator voting for themselves is not a signal, and that a prize split across
three placings has to add up to the prize.

## The deadline is computed, never stored

The app stores `submit_deadline` as a column and **never compares it to
anything** — `api_submit` only checks `status != "open"`. So a submission a week
late is accepted, as long as nobody has manually moved the challenge to
`judging`.

That isn't untidiness. A competition that accepted a late entry and then awarded
a prize is one that every entrant who made the deadline can challenge.

```python
stack.phase(brief.id, now=30)   # "open"    — the deadline itself
stack.phase(brief.id, now=31)   # "judging" — nothing had to run
```

`open | judging | awarded` is derived from the clock and the awards. There is no
midnight job and nothing to forget. The engine also refuses to create a
challenge without a deadline at all — without one, "late" has no meaning and no
result is defensible.

Same lesson as RightsForge's option term, in a place where it matters more:
**state that depends on time must be computed.**

## Two checks the app never makes

| | |
|---|---|
| A creator votes for their own entry | nothing checks |
| The sponsor votes | nothing checks |

Votes are described in the app as *"the signal the sponsor sees when picking a
winner"*. A self-vote is a thumb on that scale, and a sponsor voting before
judging lets them appear to follow a signal they created. Both are refused here.

## Telling support from a brigade

Twenty votes from twenty people who also voted on other entries is a result.
Twenty from twenty accounts that voted for nothing else is a brigade. **A raw
count renders both as "20".**

`integrity()` reports the difference:

```
{"signal": "concentrated-support",
 "detail": "10 of 10 voters voted for nothing else in this challenge (100%)",
 "concentration": 1.0}
```

**It reports; it does not discount.** Disqualifying somebody's votes is an
accusation, and an engine that makes it silently is one nobody can argue with —
the same reason StoryAtlas offers both resolutions to a contradiction instead of
picking one. The count stays untouched and the evidence sits beside it.

The ranking is also never reordered by trustworthiness. Reordering would hide
the disagreement between *most votes* and *most credible votes*, and that
disagreement is the entire point.

Thresholds (`SINGLE_USE_VOTES`, `CONCENTRATION_FLAG`) are named constants, not
buried literals — they are policy, not fact, and whoever runs the competition
should be able to see and change them.

## A tie has no winner

`leader()` returns `None` on a tie rather than picking one. There is no honest
way to break it here, and quietly choosing the lower id is a result decided by
insertion order.

## Prizes that add up

The app awards one winner one number. Most real briefs pay a runner-up, and once
more than one person is paid the arithmetic stops being obvious — 1/3 each of
£50 is 1666.66p, and "about a third" is not an amount anyone can be paid.

Allocation goes through the **platform's** money splitter (integer pence,
largest remainder), so the placings always reconstruct the pot exactly. Asserted
across every prize from £0 to £30 against every placing count, not against a
hand-picked example.

An unusual number of placings needs an explicit split — **guessing at how to
divide a prize is not the engine's decision to make.**

## Money moved to the platform

`money.py` began inside RightsForge splitting royalties. CreatorStack needed the
identical thing for prizes, so it moved to
`creativeos_engine/platform/money.py`. The constitution's own test settles it:
*"can another application reuse this capability? If a capability is universal,
build it into CreativeOS."*

Two applications rounding money by slightly different rules is exactly the class
of bug nobody finds until a payout is short.

## Boundaries

Publishes `challenge.posted`, `submission.received` and `challenge.won`, and
holds **no reference to FrameVault**. A test parses the engine's imports and
fails if it ever reaches sideways to a sibling application.

The award is recorded **before** `challenge.won` is published, tested with a
spy — a listener that reacts by asking who won cannot arrive before there is an
answer. Same ordering rule as RightsForge's grants.

## Honest limitations

- **Time is a plain comparable.** The tests use integers; a `datetime` works
  unchanged, since the engine never does arithmetic on time beyond `<`.
- **Concentration is one signal, not fraud detection.** It cannot see IP
  addresses, account age or timing, which is where real brigade detection
  lives. It reports what it can compute and says so.
- **No payment execution.** It decides who is owed what; moving money is not the
  engine's business.
- **In-memory.** Persistence is the application's job.
