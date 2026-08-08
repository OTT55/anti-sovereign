# Reconciliation findings — "doesn't let anyone know how to reconcile places with people"

**Update 2, 2026-08-03:** four more things, after testing against the real
`voluntas` universe surfaced what the first round of fixes missed:

- **Character-to-character relationships are now typed, not just generic
  "linked."** The dependency parse was already computing real subject-verb-
  object triples ("Clara gave Marcus the sword") for every sentence — but
  only the ones recognized as *event* verbs ever got used; everything else
  was silently discarded, which is the real reason Meridian's relationships
  read as family/ally/enemy while a draft-imported universe's read as a flat
  "everyone's linked" graph. Now a non-event relation between two known
  characters creates a real typed edge (`kind: 'give'`, etc.), and it wins
  over the generic co-occurrence edge for that same pair rather than both
  existing.
- **The organization-extraction fix from Update 1 only affected future
  imports** — "Norse" and "The Life, Death and Resurrection of Christ" were
  still sitting in voluntas's already-committed data, still generating
  Governance-gap warnings. That's a real miss on my part: fixing the
  extraction code doesn't retroactively fix what's already committed, and I
  should have caught that the same way I already had for character status.
  Removed both (plus "Constant," same false-positive class) from voluntas
  directly. Left BALEN-KAMER/Metas/navy alone — plausibly real, not my call.
- **A draft can now be reopened and edited**, not just imported once and
  archived. New endpoints list and fetch a universe's past drafts; a
  "✎ Edit a previous draft…" menu entry loads one back into the existing
  paste-and-analyze flow. Re-committing reuses existing events/scenes by
  title instead of duplicating them, so revising a draft is now additive,
  not accumulative.
- **The organization/canon-noise problem is bigger than one fix, and I'm
  flagging it rather than patching around it.** Genre-tuned severity already
  existed (Governance-gap is "info" outside political/fantasy), but that
  doesn't stop *any* oddly-capitalized phrase in *any* genre's prose from
  becoming an "organization" candidate in the first place — a comedy script
  would extract its own joke phrases the same way voluntas's prologue did.
  The real fix is confidence-flagging extraction itself (surface it for
  confirmation, don't silently trust it) — the same principle already used
  for coreference and entity typing — not more genre-specific exclusion
  rules, which wouldn't generalize to the next genre's own quirks.

**Update 1, 2026-08-03: the concrete bugs below are fixed, deterministically, no
model involved.** Every fix is regular code — reviewable and revertable in a
diff exactly like any other change, nothing hidden behind a model call:

- **Event → character/location linking now actually happens.** Extraction
  already worked out which known characters/locations a sentence involves;
  `api_draft_commit` just never used it. Now it does — every draft-imported
  event that names someone creates a real `relationships` row, instead of
  landing with `links: []` like all 11 of voluntas's events did.
- **A death or birth event now updates the character it's about.** If an
  event is categorized `death`/`birth` and names a known character, that
  character's `status`/`death_year`/`birth_year` gets set — but only if it
  wasn't already set, so a hand-corrected record can never be silently
  overwritten by a re-import. This is the direct fix for "dead people are
  alive": it was never that the app disagreed, it's that nothing ever told
  a character record about their own death.
- **Pronouns can't become characters anymore.** "We", "You", "Everyone",
  "Someone", and similar were missing from the stopword list — they're in it
  now. Verified directly: a test draft with "We walked in. Everyone was
  silent. You could feel it." produces zero pronoun characters.
- **A second merge pass catches untitled duplicates.** "Jemimah" and
  "Barrister Jemimah Selman" didn't merge because "Barrister" wasn't in the
  curated title list — now anything whose words are a subset of a fuller
  name's words merges into it, regardless of what the untitled word is.
- **Organizations need structural evidence, not just capitalization.**
  NER-contributed org candidates now have to contain an actual org keyword
  (order/council/compact/fleet/etc.) — kills "Norse" and "The Life, Death and
  Resurrection of Christ" being filed as factions, while keeping "Order of
  Ravens"-style catches.
- **A stray quote/newline can't get baked into a stored name anymore** —
  sanitized both where names are extracted and, more importantly, at the
  actual commit boundary, since a hand-edited review-screen name never passes
  through extraction at all.

All six verified end-to-end against an isolated disposable test universe
(never against your real data) with prose deliberately shaped like voluntas's
first-person, fragment-heavy style — plus a full regression check confirming
Meridian's two planted canon warnings are still exactly the same, byte for
byte, as before any of this.

**Deliberately not done, and why:** surfacing `narrative_state()` in the
Timeline UI, a prose-synopsis export, confidence-flagged extraction, and
generalizing impact-preview beyond characters (§5 below) are still open —
those are product-shape decisions, not bugs, and are worth doing once you've
seen these fixes land on real material.

**On wiring in a model:** not done this round, deliberately. There's no
`ANTHROPIC_API_KEY` in this environment right now, so I have no way to test
Claude's side of anything today — building it without being able to verify it
would repeat the exact problem you're frustrated about. And everything above
turned out to be a coverage gap, not a reasoning gap, so a model wasn't
actually the fix for what you pointed at. Full reasoning in the chat response.

---

**Original findings, 2026-08-02** (kept below as the record of what was
actually observed before the fix, tested live and read-only against your real
`voluntas` universe, id 16):

---

## 1. The concrete bug behind "dead people are alive"

Every one of the 19 characters draft-imported from `voluntas` comes back as
`"status": "alive", "birth_year": null, "death_year": null` — **all 19, no
exceptions.** That's the literal mechanism: nothing in the pipeline ever writes
`status: "dead"` or a `death_year` unless the source text states an explicit
absolute year next to an explicit death phrase in a very specific pattern. A
death that's narrated in prose ("Stars die.") never touches any character
record, even when it's extracted as its own event.

Worse, the event that's clearly *about* death — id 74, title "Stars die." —
has `"links": []`. Every single event in your timeline does. Not one of the
11 extracted events is connected to a character, location, or organization.
The `relationships` table is supposed to be "the spine — everything reads from
it," and for this import it's carrying zero event-to-entity edges. That's the
literal meaning of "doesn't reconcile places with people": the pieces exist as
separate rows: characters here, events there, nothing joining them.

**Root cause, most likely:** my dependency-parse relation extraction (built and
tuned against Meridian's clean, expository, almanac-style seed text — "Two
centuries after Earth seeded the Meridian system...") doesn't find clean
subject-verb-object patterns in first-person literary narration with dialogue,
fragments, and digressions. It has no fallback that says "I couldn't find a
structured relation here" — it just produces nothing, silently.

## 2. A second, different bug: the graph that DOES exist is meaningless

`narrative_state` for `voluntas` shows every character "linked" to roughly
15–19 other characters, all with the same generic `kind: "linked"` — not
family/ally/enemy/member like Meridian gets, just an undifferentiated clique.
This looks like a coarser fallback tier (probably co-occurrence-in-text) firing
instead of typed extraction. The practical effect: the graph technically
"connects" everyone to everyone, which carries exactly as much information as
connecting no one — you can't tell a meaningful tie from noise.

## 3. Entity typing is inverted on this prose: it keeps the noise, drops the signal

The character list includes **"We", "You", "Everyone"** — pronouns, not
characters — sitting in the same table as real people. Meanwhile genuinely
distinctive named characters mentioned in the timeline text itself —
*Kolakanwi Van Tegha*, *Jalakanwi Van Tegha*, *Chira* — never made it into the
character table at all. And organizations picked up **"Norse"** and **"The
Life, Death and Resurrection of Christ"** — mythological/theological
references inside a philosophical prologue, mistaken for in-world factions,
because the heuristic pattern-matches capitalized noun phrases without
distinguishing "a faction in your story" from "a reference your narrator
makes." A real title-based duplicate also slipped through: "Jemimah" (id 123)
and "Barrister Jemimah Selman" (id 130) never merged, because the merge logic
only strips a small curated list of political/fantasy titles (admiral,
chancellor, lord…) — "Barrister" isn't in it, so nothing told them apart from
the same person twice.

There's also a small data-corruption bug: one character name is literally
`"Hexi\n \"Hexi"` — a stray newline and quote character baked into the stored
name, meaning quotation/dialogue punctuation is leaking into name extraction.

## 4. Temporal reasoning mostly didn't fire either

Only 2 of 15 timeline entries got a resolved year (2037, 2042 — both from
explicit `DD/MM/YYYY` stamps in the text). Everything else stayed `null`. The
running-clock resolver I built chains relative phrases like "ten years later"
— this prose doesn't give it that scaffolding, so it has nothing to chain.

**None of this needs AI to fix.** Every one of the four problems above is a
heuristic/coverage gap, not a reasoning gap — a wider title list, a
co-occurrence-vs-real-relation distinction, a "flag pronouns as low-confidence,
ask don't guess" check (the pipeline already does this elsewhere — it should
here too), and sanitizing quote characters out of extracted names. That lines
up with what you said: this doesn't need artificial intelligence, it needs
better structure.

---

## 5. Your actual question: what's the *actionable* thing a user gets from all this?

Honestly, right now: not much. Nineteen character rows and eleven events is
*data*, not insight. The gap between "we extracted rows" and "here's something
useful about your story" is the real product gap. Four concrete directions
(options, not a plan I've started):

1. **Surface `narrative_state()` where a reader would actually want it.** It's
   built and correct (verified against Meridian this session) but invisible —
   nothing in the Timeline or Graph view ever calls it. A "world state as of
   this point" panel, sitting right in the Timeline, would be the first real
   payoff of everything that's already built.
2. **A refined synopsis, not a form dump.** Instead of a JSON-shaped character
   sheet, generate readable prose from the structured data: *"As of Year 2042:
   Kal, Rienne, and Hani are alive; BALEN-KAMER has no leader on record."* That's
   the "refined version, not a draft" you're asking for — same data, written
   like a briefing instead of a database export.
3. **Confidence-flagged extraction, surfaced to the user.** "We"/"You"/
   "Norse"/"The Life, Death and Resurrection of Christ" should come back
   tagged *low confidence — is this really a character/organization?* rather
   than sitting in the table with the same authority as Kal or Hani. The
   pipeline already has an "ask, don't guess" convention elsewhere (coreference,
   entity typing) — this is the same principle applied to the whole-entity
   decision, not just its attributes.
4. **Generalize impact preview beyond character fields.** The pattern I just
   shipped (apply hypothetically → check → roll back) is architecturally
   proven now — the harder part isn't the mechanism, it's deciding which forms
   (a new relationship? an event?) earn a Preview button. You're right that
   this adds real complexity; the good news is it's the *same* trick each time,
   not a new one per entity type.

## 6. Design lesson from Obsidian / Notion / NotebookLM's mind map

Obsidian's graph works because links are **explicit and sparse** — a person
typed `[[this connects to that]]` on purpose. What `voluntas` produced is the
opposite: **dense and generic** (everyone linked to everyone, same edge kind).
NotebookLM's mind map is closer to the right shape for a story: it's
**hierarchical**, not a flat peer graph — main thread, sub-threads branching
off it. The lesson isn't "copy any of these tools" — it's that *sparse + typed
+ hierarchical* beats *dense + generic + flat*, and right now the fallback
tier that fired on your prose produces the flat, generic kind. Worth keeping
in mind when deciding what "good" looks like for the graph view, not just for
extraction quality.

## 7. Is this running with Ollama right now?

**No.** Checked directly: `ollama`/`Ollama` doesn't appear anywhere in
`app.py` or `requirements.txt`. The Ollama testing earlier this session was a
standalone benchmark script hitting the Ollama server directly — never wired
into the app itself. That was deliberate: the verdict on Ollama was that
`llama3.2:3b` confidently invents a different specific wrong year every run
for a question it can't actually answer, rather than saying "unknown" — the
opposite of safe for exactly the kind of reconciliation work described above.
So the fixes in §1–3 are better solved the way you said you wanted: structurally,
not by pointing a local model at the mess.

---

## What I did NOT do this round

No code changed. This is the "retest, rethink, look at it strategically" pass
you asked for — I tested for real, found the actual mechanism instead of
guessing at your description, and I'm handing it back before doing anything
else. Go poke at it as a user; come back with what you want prioritized.
