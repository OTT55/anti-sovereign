# What changed, and why — Phases 8 to 11

Written for you to read as a user, then come back and tell me what is still
wrong. Everything below is in `excess engine/creativeos/apps/storyatlas/`.
Nothing outside that folder was touched.

**262 tests pass** (was 162). The whole CreativeOS suite is **584** (was 484).

---

## 1. The bug you reported

> *"There are people that are supposed to be dead in the new future, but they
> are alive, which makes no actual sense."*

You were right, and the reason turned out to be precise rather than vague.

Before this, a character's death was checked against **dated events naming them
as the grammatical subject**. Three ways of being alive after your own death
went straight through:

1. **Appearing in a scene.** Scenes had *no date at all*. A scene set in 1160
   could list a character who died in 1135, and nothing ever compared the two
   numbers, because one of them did not exist.
2. **Being the object rather than the subject.** *"The council summoned Aldric"*
   makes Aldric the patient. The lifespan check never looked there.
3. **Standing in a place.** A place has a lifetime too — founded, fallen — and
   nothing reconciled a person's years against a location's.

### What it does now

`presence.py` does three things, all arithmetic:

- **Dates every scene**, which nothing did before, from the events inside it,
  its own time expression, or the previous scene.
- Builds a **typed existence interval** for every entity — `[begins, ends]` —
  keeping people, places and organisations apart.
- **Intersects** them. `[born, died] ∩ {year}` is either empty or it is not.
  Empty means a contradiction, and there is nothing to infer or guess.

On the test draft it now says:

```
[error] Mara Sadel died in 1135, but appears in scene 3, dated 1160 — 25 years later.
```

### A second bug I found while fixing the first

Your draft had *"Dawnhold was founded in 1090. He was crowned at the age of
thirty."* The engine resolved **"he" to the castle** — it was simply the nearest
thing mentioned.

The visible damage was nowhere near the cause. With the coronation attached to
a castle, it had no birth year to count thirty from, so it never got dated, so
the *next* sentence's "three years later" anchored to the **founding** instead —
and a death landed **42 years early**. One pronoun silently re-dated half the
draft, and every downstream check inherited the error.

Fixed by resolving pronouns **after** typing rather than during extraction, so
the engine knows a castle is not a "he" and can reach past it to the person
meant. It still never chooses between two people.

### And one false alarm I had to remove

My first version flagged a character as appearing *twelve years before he was
born* — in the very scene that narrates his birth. The scene covered 1090–1102
and I had collapsed it to a single year.

Scenes now carry a **span**, not a point, and a contradiction is reported only
when *no* year in the span works. A checker that cries wolf gets switched off,
and then it catches nothing at all.

---

## 2. Grouping characters, not just events

> *"He's grouping the timelines well, but he does not group characters when they
> appear within the timeline."*

Correct — `by_period()` bucketed **events** into eras and stopped. `grouping.py`
adds the people:

- **Eras** — a slice of time and its cast. *Alive* is computed from the
  intervals; *on the page* is counted from the text. **The gap between the two
  is the useful number**, because "alive but never appearing" is where drafts
  quietly lose people. It is the question you cannot answer by re-reading: *who
  did I forget?*
- **Circles** — who keeps turning up with whom, as connected components over
  shared scenes. Chosen over a clustering algorithm because a component is
  *explainable*: I can show you the exact chain of scenes that put two
  characters in one group.
- **Generations** — banded by birth year, so a saga reads as generations.
- **A grid** — every character down the side, every era across the top:

```
              1   2   3   4   5   6   7   8   9
Aldric Vane      +   ·   ·   #   ·   ·   #   #
Kesh Oru                                     +
Mara Sadel   ·   ·   ·   ·   x

  + born   # on the page   · alive, offstage   x died
```

---

## 3. What you can actually *do* with it

> *"You have all the places in this thing. What will you do with it? What
> actionable thing can you take from it?"*

A list of thirty findings is not a plan. `worklist.py` ranks them, and the
ranking is the idea:

**Leverage.** When the solver dates an event by arithmetic, it does so against
an anchor. Fix a wrong anchor and every date computed from it moves too. So a
stated year that anchors nine computed dates is worth nine times one that
anchors none — and **three separate contradictions may all be one wrong number
upstream**. The worklist counts those dependencies and sorts by them, so the
first item is the one that unblocks the most.

It is a count of real things, not a score. You can check it by looking.

**Every finding carries its options.** Not "this is wrong" but:

```
## F01  Mara Sadel died in 1135, but appears in scene 3, dated 1160 — 25 years later.
      1. Move Mara Sadel's death (currently 1135) — re-dates every check against her
      2. Re-date this scene instead — moves this event; leaves the lifespan alone
      3. Mark it deliberate (a flashback, a vision, a ghost) — stops the engine reporting it
      4. Intentional — stop reporting this
```

Both resolutions are offered because **which of the two dates is wrong is your
decision**. An engine that silently picks one has invented a fact.

`next_action()` names the single highest-leverage thing to do right now, because
"here are forty findings" is not an answer to "what do I do next".

---

## 4. The refined version, and interactive tweaking

> *"It should have an option to produce not even a draft, but a refined version.
> And the tweaking should be interactive."*

`revise.py`. A one-shot "cleaned up draft" would be the wrong shape, for the
reason above: almost every contradiction has more than one honest resolution and
nothing in the text distinguishes them.

So the loop is: **the engine finds and ranks, you decide, the engine applies it
and re-reads the whole draft from scratch.**

That last part is the design. It is slower than patching in place, and it is the
only way to answer the question that matters after any edit:

> **what did that just break?**

```python
session = Session(draft)
fix = session.issues()[0]
print(session.preview(fix, fix.options[0], value=1150).render())
#   1 resolved, 0 introduced — an improvement
session.apply(fix, fix.options[0], value=1150)
print(session.refined())
```

`preview()` shows both sides before anything is committed. A revision that fixes
one contradiction and quietly creates two is worse than no revision.

The refined draft is **your own words with your own decisions folded in** —
pronouns resolved where you said so, dates made explicit where you gave one,
deliberate anomalies marked as deliberate. Not a rewrite. Annotations go in
brackets so your sentence is left exactly as written and the note is visibly the
engine's.

`undo()`, `reset()` and a `transcript()` of what each decision did are all there.

**A related fix:** the "mark it deliberate" option originally did nothing —
it annotated the text but the engine kept reporting the problem anyway. Now a
`[deliberate: ...]` marker in a sentence genuinely exempts it. The marker lives
in your draft rather than in a database beside it, so it survives a copy-paste
into another editor and you can see it. A suppression you cannot see is one you
will trip over again in six months.

---

## 5. The mind map — and why an Obsidian vault instead

> *"How does something like this work with a mind map? NotebookLM's mind map
> makes more sense at this point."*

It does, and the reason decides what I built. Obsidian's graph is useful **not**
because it draws circles and lines — that part is nearly decorative — but
because every node is a real note you can open, and every link was put there by
something that knew what it meant. A picture of a graph is a poster. A graph you
can walk is a tool.

`mindmap.py` produces both:

- **A graph** — nodes and weighted edges (`relation`, `appears-with`, `located`,
  `during`), plus Mermaid and a text outline.
- **A vault** — one markdown note per character, place, organisation and era,
  cross-linked with `[[wikilinks]]`. `write_vault(reading, folder)` and open the
  folder in Obsidian. No import step, no plugin.

The vault is the point. **The findings live in the notes beside the facts**, so
the contradiction about Mara is *on Mara's page*, where you will be when it
matters, rather than in a report you have to remember to open.

---

## 6. Ollama — the straight answer

**Yes, Ollama is installed and running on this machine** (`llama3.2:3b` locally,
`gpt-oss:120b` via the cloud endpoint). I checked.

**No, the engine has never called it, and after all this it still does not.**

Not an oversight — a decision, and I want to be honest that it is mine, so you
can overrule it. Everything the engine concludes is arithmetic over dates.
`1160 > 1147` is not a matter of opinion; it is checkable by you and it comes
out the same every time. Handing any of that to a model trades a proof for a
guess and makes the answer unreproducible — which is the exact failure you
reported in the first place. The reconciliation you asked for **cannot** be
built on something that might answer differently tomorrow.

There is now exactly one seam, `polish.py`, and it is **off unless switched on**:
after you resolve "he" to Aldric, the resulting sentence is grammatically blunt,
and smoothing it is a language task with no judgement in it.

Its fence is the part worth checking: **the model's output is rejected unless
every name and number survives it.** Facts are extracted from input and output
and compared as sets; any change and your original sentence comes back untouched
with the reason recorded. The worst it can do is nothing.

```python
polish.report()
# "Ollama is running (models: llama3.2:3b, gpt-oss:120b-cloud). The engine calls
#  it nowhere by default; polish.smooth(..., enabled=True) is the only seam, and
#  it may rephrase a sentence but not change a fact."
```

If you want the model doing more than this, say so and I will build it — but I
would want it behind the same kind of fence, where a model proposes and
arithmetic decides.

---

## What I'd want you to try, and what I expect to hear back

```bash
python demo_revision.py
```

Then feed it a real chapter. The things I most expect to be wrong:

- **Scene detection on real prose.** My test drafts use `***` and `CHAPTER`
  markers. Your actual formatting will break something.
- **Carried scene dates.** Long stretches with no time signal inherit the
  previous scene's year. That is an assumption, marked as one, but on a real
  manuscript it may inherit for far too long and go quietly wrong.
- **Circles on a large cast.** Connected components merge aggressively — one
  character who meets everyone can pull the whole book into one circle. There is
  a `minimum` threshold, but I have not tuned it against anything real.
- **The offstage count.** It should be the most useful number here. It may also
  be the noisiest.

Tell me which of those actually bit you and I will fix the real one rather than
the one I guessed at.
