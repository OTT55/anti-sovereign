# StoryAtlas Engine

The domain authority for **narrative comprehension**, sitting on top of
CreativeOS. Deterministic: no API calls, no model, no training. Same draft in,
same reading out, every time.

```bash
python demo.py              # what it understands
python demo_revision.py     # what you can do about it
python -m pytest -q         # 262 tests
```

Eleven phases are built. Phases 1–7 comprehend a draft: segmentation, entity
typing, scenes, relationships, canon rules, structure, and the coordinating
report. Phases 8–11 make that understanding usable:

| Phase | File | What it adds |
|---|---|---|
| 8 | `presence.py` | Reconciles **people with places and time** — dates the scenes, builds typed existence intervals, and intersects the two |
| 8 | `grouping.py` | Groups the **cast inside the timeline**: eras, circles, generations, and a character-by-era grid |
| 9 | `worklist.py` | Ranks every finding by **leverage** — how many other facts depend on it — and attaches applicable options |
| 10 | `revise.py` | An **interactive revision session**: preview, apply, undo, and a refined draft |
| 11 | `mindmap.py` | The draft as a graph, and as a linked **Obsidian vault** |

See [WHAT_CHANGED.md](WHAT_CHANGED.md) for why each of those exists and what
was wrong before it.

## The problem it solves

The Story Atlas app extracts **names** well. It cannot understand what is
*happening*. In `companies/creativeos/story-atlas/app.py`, an event is stored as
the raw sentence plus a keyword-guessed category, with `year: None` unless a
literal year appeared. Nothing links an event to the people in it, and
`"three years later"` is detected then discarded.

So the app cannot answer *who died*, cannot order events, and cannot group
anything. That is the gap this engine closes.

## What it does

Given a draft stating **two** dates:

```
Chancellor Aldric Vane was born in the year 1102 in the city of Dawnhold.
He was crowned at the age of thirty.
Three years later, the Meridian War began.
Mara Sadel died that same year at Dawnhold.
Aldric was killed by Tobin Reyes two years later.
A decade later, Tobin Reyes founded the Order of the Broken Crown.
In 1155, Mara Sadel signed the Dawnhold Accord.
```

it solves for the other five:

```
· 1102   birth      Chancellor Aldric Vane      · stated
→ 1132   accession  Chancellor Aldric Vane      → computed  (1102 + 30)
→ 1135   battle     Meridian War                → computed  (1132 + 3)
→ 1135   death      Mara Sadel                  → computed  (same year)
→ 1137   death      Chancellor Aldric Vane      → computed  (1135 + 2)
→ 1147   founding   Tobin Reyes                 → computed  (a decade later)
· 1155   political  Mara Sadel                  · stated
```

and then catches the continuity error:

```
[lifespan] Mara Sadel died in 1135, but this is dated 1155.
           "In 1155, Mara Sadel signed the Dawnhold Accord."
```

## How, without AI

A time expression is not a *value*, it is a **constraint**. "Three years later"
is the equation `this = previous + 3`. Collect every such equation and the
unstated dates can be solved for by propagating to a fixpoint — ordinary
arithmetic over a dependency graph.

| Stage | File | Job |
|---|---|---|
| Segmentation | `comprehend/segment.py` | Sentences that survive "Dr." and "J. Varo"; clause splitting so two events in one sentence stay two |
| Mentions | `comprehend/mentions.py` | "Chancellor Aldric Vane" = "Aldric" = "Vane"; conservative pronoun carry-over |
| Events | `comprehend/events.py` | `(kind, agent, patient, place, time)` — who did what to whom, with passive handling |
| Time | `comprehend/temporal.py` | Time expressions read as constraints, not values |
| Solver | `comprehend/solver.py` | Propagate to a fixpoint; report conflicts and what stayed unknown |
| Reading | `reading.py` | Grouping by kind / person / period, and the questions |

## It asks instead of guessing

Where it cannot tell, it produces a **question**, not a fact:

- `who` — the clause has no named subject
- `when` — the event never got a date
- `pronoun` — "he" was carried over from the previous sentence; confirm?
- `conflict` — a clause states a year *and* a relation that disagree
- `lifespan` — someone acts outside their own life

Every question cites the sentence that prompted it, and offers candidates where
it has them. The writer confirms rather than transcribes, which is the intended
inversion: today the app makes the user enter everything.

## Relationship to CreativeOS

`bridge.py` writes a reading into the CreativeOS graph, and the division of
labour is the whole architecture:

- **StoryAtlas** computes a lifespan — knowing that a death bounds a life is
  narrative knowledge.
- **CreativeOS** stores it as `ValidWindow(1102, 1147)` on an `alive` assertion,
  and from then on any fact outside that window contradicts it automatically.
  That check is universal, so it lives there.

Only confident readings are written. Anything questioned is held back until a
human confirms it — a draft is not evidence until someone says the engine read
it correctly.

## What else it does

Beyond dates and events (`analyse(text)` returns all of it):

- **Entity typing** — character / location / organization / event, from how the
  prose uses a name. Works on invented words.
- **Scenes** — boundaries, cast, place, time, and the events in each.
- **Relationships** — possessive, appositive and predicate forms, with kinship
  inverses derived (so "who are Aldric's children" is answerable from "Mara is
  Aldric's daughter").
- **Canon rules** — an organisation acting before its founding, a character in
  two places at once, someone acting before they were born, relationships
  between lives that never overlapped, a title held twice.
- **Structure** — character threads, presence gaps, pacing, loose ends.

## It records only what the text asserts

A trigger verb is not enough. These put **nothing** in the timeline:

```
Aldric Vane did not die in 1147.          negated
If Aldric had died, the war would end.    hypothetical
Aldric Vane will die in 1147.             future
Did Aldric Vane die in 1147?              a question
```

Each is surfaced as a question instead — the engine saw it and deliberately
kept it out, which is different from missing it. A false death would bound a
lifespan and drag every date chained from it, so this is the one place where
recording nothing is strictly better than recording a guess.

## Honest limitations

- **Names sharing a word are only separated when the head noun gives it away.**
  A person shortens either way ("Aldric Vane" → "Aldric" or "Vane"); a named
  thing shortens by its head noun only ("Dawnhold Accord" → "the Accord", never
  "Dawnhold"), which keeps a treaty from swallowing the city it was named
  after. Two *people* sharing a surname still merge — CreativeOS's Verification
  Engine reports that class as an *ambiguity* rather than resolving it.

- **Role assignment uses word order**, not a parser. It is right on ordinary
  prose and wrong on genuinely tangled sentences — which is why every event
  carries a confidence and low-confidence ones become questions.
- **Pronouns resolve to the most recent person**, reaching past places and
  organisations to get there but never searching further and never choosing
  between two people. Guessing further produces confident nonsense.
- **A scene's date is only as good as its signal.** Where the text gives no
  time at all, the previous scene's year is assumed and marked `carried`;
  contradictions resting on a carried date are reported as warnings, never
  errors.
- **A grouping is not a judgement.** "Alive but offstage for five eras" is a
  fact about the draft. Whether that is a problem is the writer's call.
- Sub-year units ("three days later") order events but do not move the year.
