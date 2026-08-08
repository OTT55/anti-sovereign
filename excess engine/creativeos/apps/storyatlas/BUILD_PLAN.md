# StoryAtlas Engine — Build Plan

StoryAtlas is the domain authority for narrative comprehension (Constitution
v2.0). Its engines: Story, World, Character, Canon, Timeline, Civilization,
Geography, History, Organization, Culture, Language, Map, Narrative
Intelligence.

## Where things stand

The app in `companies/creativeos/story-atlas/` is real and works — spaces,
character database, timeline, graph, canon checks, assistant. Its limit is
comprehension: it extracts names well, and understands nothing else. This engine
is the comprehension layer underneath it.

| StoryAtlas engine | State |
|---|---|
| **Timeline** | **Real.** Time expressions as constraints, solved to a fixpoint. Stated vs computed dates distinguished; conflicts reported. |
| **Character** | **Partial.** Characters typed and identified, aliases resolved, lifespans derived, per-person event trails. Missing: goals, motivations, arcs — the app holds those by hand. |
| **Canon** | **Real.** Six rules plus lifespans and self-contradicting dates, each citing the records in conflict. Missing: power/magic-system consistency and retcon tracking. |
| **Story** | **Real.** Scenes with cast/place/time/events, character threads, pacing, loose ends. Missing: acts and explicit arc modelling. |
| **World / Geography / Culture** | **Partial.** Places are typed as locations; not yet modelled (no maps, cultures, calendars). |
| **Organization** | **Partial.** Organisations are typed; not yet modelled (no membership, leadership, founding chains). |
| **History / Civilization** | **Not built.** |
| **Language / Map** | **Not built.** |
| **Narrative Intelligence** | **Real.** `analyse()` produces a full draft report. |

## Phase order

**Phase 1 — Comprehension core.** ← *built, 59 tests*
Segmentation, mentions and aliases, events with participants and roles, time as
constraints, the solver, grouping, questions, and the CreativeOS bridge.

**Phase 2 — Entity typing.** ← *built, 71 tests*
Every name is now typed as character / location / organization / event from how
the prose uses it. The strongest evidence is the event roles extraction already
produced — whoever acts is a person, whoever is born or dies is a person,
whatever a preposition marks as the setting is a place — with surface patterns
as fallback. Works on invented words: "Ravenmoor" is a place because the text
says "fled to Ravenmoor", not because a gazetteer knows it. Per-person grouping
now excludes organisations and wars, which was the Phase 1 gap. A name the
evidence splits on, *or gives nothing for*, becomes a `type` question rather
than a silent guess.

**Phase 3 — Scene and structure.** ← *built, 99 tests*
Scene boundaries from explicit markers (`***`, `CHAPTER TWO`, sluglines), blank
lines, and setting shifts; who is present, where, when, and which events belong
to each. A place carries forward until the text names a new one, because prose
states a location once and then assumes it. Feeds the app's scene database
instead of the writer typing it.

**Phase 4 — Relationship extraction.** ← *built, 99 tests*
Possessive ("Aldric's daughter Mara"), appositive ("Mara, daughter of Aldric")
and predicate ("married", "served under", "betrayed") forms. Kinship inverses
are **derived**, since a graph storing only "Mara is Aldric's daughter" cannot
answer "who are Aldric's children" — the same fact asked the other way round.
Gendered inverses are deliberately not invented: "parent" is safe, choosing
*father* over *mother* is not.

**Phase 5 — Canon rules.** ← *built, 124 tests*
Six deterministic rules beyond the lifespan check: an organisation acting before
its founding, a character in two places in one year, someone taking part in
something before they were born, a relationship between lives that never
overlapped, and a title held by two people at once (with an orderly handover
correctly not flagged). A rule that cannot be evaluated stays silent — a
checker that cries wolf gets switched off, and then it catches nothing.

**Phase 6 — Narrative structure.** ← *built, 124 tests*
Character threads through the draft, presence gaps, event density per stretch,
loose ends (a character in one scene, never seen again), and passive characters
present but never acted upon. Descriptive, never evaluative: "front-loaded" is
a fact about the text; "badly paced" would be a judgement this cannot make, and
saying so is more useful than dressing a word-count up as insight.

**Phase 7 — Narrative Intelligence.** ← *built, 124 tests*
`analyse(text)` — the single entry point. Coordinates comprehension, typing,
scenes, relationships, the timeline, canon and structure into one draft report.
Adds almost no logic of its own. The ordering rule is the only judgement:
**errors before absences**, because a continuity break makes the draft wrong
whereas a missing date makes it incomplete, and mixing the two teaches a writer
to skim.

## On whether a model is ever needed

OTT's direction: no API calls, no AI, solve it in mathematics if possible. Phase
1 confirms that is realistic — dates, roles, grouping and continuity are all
deterministic, and determinism is a feature for a continuity tool, not a
compromise.

The honest boundary: **judgement** cannot be computed this way. "Is this
character's arc satisfying?" or "does this power level break the established
magic system?" are not arithmetic. Phases 2–5 are all still deterministic. If a
model is ever wanted, Phase 6 is the first place it would earn its cost, and
CreativeOS's AI Orchestrator is where it belongs — as infrastructure, behind an
interface, never in this engine's core.

Training a model is not proposed: it needs labelled narrative data that does not
exist and would have to be created by hand.

## Status

**All seven phases built and tested — 124 tests**, ~0.3s, deterministic, no network. Working
rhythm as elsewhere: one phase at a time, run its tests, explain it plainly,
stop and wait.

This engine does not modify the app in `companies/creativeos/story-atlas/`.
Wiring the app to it is a separate decision for OTT.
