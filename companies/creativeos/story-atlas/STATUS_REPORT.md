# Story Atlas — full status report, roadmap comparison, and honest assessment

**Written 2026-08-03**, at your explicit request, because you're running low on
credits and wanted everything captured in one place before this session ends.
Nothing rushed — this covers the complete history of what's been built, what
the original plan actually promised, what's genuinely missing, and a direct
answer to "is this doomed."

---

## 1. What Story Atlas actually is

A structured operating environment for building and auditing a fictional (or
non-fictional — memoir, history) universe: characters, locations,
organizations, timeline events, scenes, and lore, all wired together by one
`relationships` table of typed edges. Two things read that graph and make it
smart:

- **Canon Engine** — audits the universe for contradictions (impossible
  lifespans, timeline violations, posthumous references, broken links,
  leaderless organizations, relationship conflicts) and names the exact
  records in conflict.
- **AI Assistant** — answers questions by *querying the graph*, never by
  inventing.

House style matches the rest of the portfolio: Flask + SQLite + hand-written
HTML/CSS/JS, no framework, no build step.

---

## 2. Complete build history

### 2a. The foundation (before this session)

- `a461d47` — Full CRUD for characters, genre-adaptive canon checks, the
  original draft-import pipeline, an empty-state fix.
- Company #11 in the original Sovereign Stack, later folded into CreativeOS
  as one of six sibling products (FrameVault, FilmCrew, RightsForge,
  CreatorStack, OTT Studio, Story Atlas), sharing FrameVault as the identity
  provider.
- The seed universe, **Meridian** (political sci-fi), was hand-authored with
  explicit, typed relationships (`family`, `enemy`, `ally`, `caused`, ...) —
  this matters later: it's why Meridian has always looked more "organized"
  than anything draft-imported.

### 2b. This session, in the order it actually happened

**Local-first NLP pipeline** (`a5f15ed`) — pushed Tier 1 (regex/heuristics)
and Tier 2 (spaCy NER) further before leaning on Claude, per your explicit
instruction that reasoning should work without API calls where possible:
- Dependency-parse relation/event extraction (real subject-verb-object
  triples off spaCy's parse tree, not "these names share a sentence").
- `fastcoref` coreference resolution (pronouns → the named entity), with an
  honestly-documented limit: it resolves pronouns, not definite descriptions
  ("the old admiral" back to a name) — a distinct, harder problem.
- A deterministic temporal offset resolver with a running-clock: "ten years
  later" chains off the last known absolute year, verified end to end.
- A NetworkX knowledge graph (centrality, shortest-path "how are X and Y
  connected").
- A narrative-state snapshot (`narrative_state(uid, as_of_year)`): who's
  alive/dead/where, as of any point in the timeline. **Built and verified —
  still not surfaced anywhere in the UI. See §4.**
- Evaluated and *rejected*, with evidence, four other tools: REBEL (worse
  output than the dependency-parse approach, and ~59 min cold model load),
  coreferee (hard version wall), AllenNLP (unmaintained, breaks on modern
  Python), `dateparser` (wrong on "ago"/"earlier"/inverts "a decade after").
- Evaluated 7 local LLM runtimes for the portfolio generally (Ollama,
  llama.cpp, LM Studio, Jan, Open WebUI, LocalAI, vLLM) — only Ollama was
  both installable and testable on this hardware. Findings written to
  `LOCAL_AI_EVALUATION.md` and duplicated into 9 locations across the
  portfolio (contextcore, veridact, canonchain, all 6 CreativeOS apps).

**Canon Engine impact preview** (`678d8d9`) — the feature both this app's own
README and its older session log flagged as the standout next step. Apply a
hypothetical ("what if this character dies in year X") inside the request's
own uncommitted DB transaction, re-run the real `canon_check()`, diff
before/after, roll back. Nothing persists unless you separately click Save.
Verified: correctly surfaced a scene-based *and* an event-based contradiction
from one hypothetical, neither of which I'd predicted by hand.

**The reconciliation investigation** — you reported dead characters showing
as alive and asked me to look, not guess. Tested live, read-only, against
your real `voluntas` universe and found the actual mechanism, not a vague
approximation of it:
- Every character defaulted to `alive`/`null` regardless of what the text
  said, because nothing ever propagated a narrated death onto a character
  record.
- Every single event had zero relationships — the extraction had already
  worked out which characters/locations a sentence involved, but
  `api_draft_commit` never used that data. This is *the* reason Meridian
  reads as organized and a draft-import doesn't: Meridian's ties were
  hand-authored; a draft-import's weren't actually being wired up at all.
- Pronouns ("We", "You", "Everyone") were being extracted as named
  characters. Real named characters in the same text were sometimes missed.
  Mythological/religious references ("Norse", "The Life, Death and
  Resurrection of Christ") were extracted as organizations.
- A title-based duplicate ("Jemimah" / "Barrister Jemimah Selman") didn't
  merge because no curated title list is ever complete.
- One character name was corrupted with an embedded newline and stray quote.

Full findings in `RECONCILIATION_FINDINGS.md`.

**Five deterministic fixes, then verified against Meridian for zero
regression, then retroactively applied to your real `voluntas` data** (with
a SHA-256-verified backup and a dry run against a cloned copy before ever
touching the real file, every single time):
1. Pronoun/indefinite words added to the stopword list.
2. A second, general merge pass: if a shorter name's words are all present
   in a longer one, they're the same entity — no title list required.
3. NER-contributed organizations now require an actual structural keyword
   present (order/council/compact/fleet/...) — kills mythological/rhetorical
   false positives.
4. Name sanitization at the actual commit boundary (not just extraction),
   since a hand-edited name never passes through extraction at all.
5. **Events now actually link to who and where they name**, and a
   death/birth event with a resolved character updates that character's own
   `status`/`death_year`/`birth_year` — additive only, never overwriting a
   value that's already set.

Retroactively applied to voluntas: 9 event relationships created, 1 corrupted
name fixed, 3 false-positive organizations removed, 3 pronoun-characters
removed (52 relationship rows they were touching cleaned up with them —
`relationships` has no real foreign key, so these don't cascade-delete on
their own), Jemimah merged into Barrister Jemimah Selman.

**Typed character-to-character relationships** (`70b8b57`) — the deeper
answer to "why is Meridian so much more organized." The dependency-parse SVO
data was already being computed for event detection, but any relation whose
verb *wasn't* an event verb ("gave", "betrayed", "trusted") was silently
thrown away — the only character-to-character edges being created were
generic "linked, appears together in the draft." Now a real verb-typed
relationship is created whenever both sides resolve to known characters, and
it wins over the generic fallback for the same pair (verified: "Clara
Whitfield gave Marcus Doyle the ledger" produces a `kind: 'give'` edge, not a
duplicate generic one).

**A genuine draft-edit feature** (`70b8b57`) — you pointed out there was no
way to revise a draft after the fact. There genuinely wasn't: drafts were
archived in a table nothing ever read back. Added endpoints to list and fetch
past drafts, a picker UI, and reused the *existing* extract → review → commit
flow (which already supported a pre-filled textarea). Also made events and
scenes idempotent on re-commit (matched by title) so re-importing an edited
draft is additive, not duplicative — verified directly: re-importing
identical text created zero new events/scenes; re-importing an edited
version created exactly the delta.

**Ollama wired in as a local Tier-3 fallback** (`70b8b57`, then two more
rounds of fixes **not yet committed**) — per your explicit instruction to
stop waiting on a Claude key and use the local runtime. `deepen_draft()` now
tries Claude if a key exists, else calls a local Ollama server directly over
`urllib` (no new dependency). This took real debugging, and it's worth being
honest about all of it:
- First live test: it correctly returned valid JSON and correctly re-typed
  entities, but confidently invented a year ("900") for a date with no
  stated anchor anywhere in the text.
- Fixed the prompt to be explicit that "year" is computed from a real
  anchor or left null, never the bare number from a relative phrase.
- Second bug, found when you reported "Deepen with AI doesn't seem to
  work" and I actually tested it rather than assuming: it was returning the
  *offset itself* as the year (a decade after → `year: 10`) — nonsense on a
  timeline. Fixed with the prompt change above; confirmed fixed directly.
- Third bug, surfaced by the same fix: tightening the prompt against
  inventing a year made the model *silently drop* a character and two whole
  events from its response instead — arguably worse, since a wrong year is
  easy to spot-check and a silently missing character usually isn't caught
  until much later. Fixed with a repair layer that runs on any deepen
  result (Ollama or Claude): anything present in the original extraction
  that's missing from the model's response, and doesn't look like it was
  merged into something that IS present, gets added back exactly as it was.
  Verified directly against a simulated response that dropped two
  characters and two events — both fully restored.
- Fourth issue: the Flask dev server runs single-threaded, so a 30-90 second
  Ollama call blocked the *entire app* — every other click would just hang
  until it finished, which is indistinguishable from "broken" to a user.
  Fixed with `threaded=True`.

**This last round (prompt fix, repair layer, threading fix) is sitting
uncommitted in `app.py` right now** — 57 insertions, 6 deletions, nothing
else touched. Everything before it is pushed to `origin/master`.

---

## 3. Original plan vs. where things actually stand

| Original MVP promise | Status |
|---|---|
| Workspace / Universes | ✅ Done |
| Character database, full CRUD | ✅ Done |
| Timeline engine | ✅ Done, but doesn't surface `narrative_state()` (built, invisible) |
| Universe graph | ✅ Done, now with real typed edges instead of only generic ones |
| AI Assistant (graph-query, not invention) | ✅ Done |
| Canon Engine | ✅ Done, extended this session with impact preview |
| Locations/Organizations/Lore/Scenes CRUD | ⚠️ **View + delete only — no create/edit UI.** Named in the roadmap since before this session; still not built |
| Canon Engine impact preview | ✅ Done this session |
| Multi-user + real auth | ⚠️ **Partially done, by a different session, not this work** — a FrameVault login gate now exists (`b538289`), but there is still no per-user *data ownership*: every logged-in account sees every universe. That's identity, not multi-tenancy |
| Export a universe bible (PDF/doc) | ❌ Not started |
| Local-first NLP pipeline (this session's big addition) | ✅ Done — coref, relation extraction, temporal reasoning, knowledge graph, narrative-state, all verified |
| Local LLM runtime evaluation | ✅ Done — 7 runtimes evaluated, Ollama wired in with real safeguards |
| Draft reconciliation (events↔people↔places actually linked) | ✅ Done this session, was a real, severe gap before |
| Draft-edit feature | ✅ Done this session |
| Confidence-flagged extraction ("ask, don't guess" for entities) | ❌ Proposed twice, never built |
| Genre-adaptive *extraction* (not just canon-check severity) | ⚠️ Partially — organization false-positives from NER are filtered now; the regex tier's own `ORG_OF_RE` pattern is still genre-blind (your own comedy-script example would still over-extract) |
| Automated regression test suite | ❌ Does not exist — every verification this session was a hand-written, one-off script, never committed as a repeatable test |

---

## 4. What's genuinely missing or fragile — no softening

- **No automated tests.** Every single fix this session was verified by a
  throwaway Python script I wrote, ran once, and discarded. There is no
  `tests/` directory, no CI, nothing that would catch a future regression
  automatically. This is the single biggest structural risk to the
  codebase's health going forward — the next session (mine or otherwise)
  has to re-derive correctness by hand every time, exactly like this one
  did.
- **`narrative_state()` is built, correct, and invisible.** Nobody using the
  app today can see "who's alive, as of this point" without me querying the
  API by hand. This was the single most-recommended, cheapest, highest-value
  next step from the reconciliation findings, and it still hasn't been done.
- **Tier 3 quality ceiling is real.** Ollama's `llama3.2:3b` is now *safe*
  (can't lie about a date, can't silently drop data) but I have no evidence
  it's actually *good*. Two rounds of defensive engineering were needed just
  to stop it from actively hurting the data — that's a meaningful signal
  about how much to trust its output even now. There is still no
  `ANTHROPIC_API_KEY` in this environment, so the one backend that's
  actually been reliable all session (Claude) has never been tested end to
  end inside the app itself, only via this conversation.
- **Extraction is still fundamentally heuristic.** Every fix this session
  was reactive — found by testing one specific real document. There is
  no reason to believe voluntas's next chapter, or a genuinely different
  genre (your own comedy-script example), won't surface a new failure mode
  nobody's hit yet. The architecture makes fixes *findable and fixable* —
  proven repeatedly this session — but it doesn't make the heuristics
  complete.
- **No per-user data isolation.** Multi-user login exists; multi-user
  *ownership* doesn't. Anyone with any FrameVault account can see and edit
  any universe.
- **A parallel, uncoordinated effort exists.** A different session has been
  building a *second*, architecturally unrelated "StoryAtlas Engine" inside
  `excess engine/` — a from-scratch deterministic constraint solver, no
  spaCy, no libraries, explicitly no AI. Two different attempts at "make
  Story Atlas's reasoning smarter" are running in this portfolio right now,
  with no reconciliation between them. That's not a code problem, it's a
  coordination one, and worth your attention regardless of what happens to
  either codebase.

---

## 5. What you need to do to make this good

In the order I'd actually do them, cheapest/highest-leverage first:

1. **Restart the server and use it.** Nothing in tonight's fixes has been
   tested against a live user session. Restart, try Deepen with AI again,
   try the draft-edit feature, look at voluntas's cleaned-up roster. Your
   hands-on testing has been the single most reliable way anything real got
   found this entire session — more reliable than me guessing at what to
   build next.
2. **Surface `narrative_state()` in the Timeline view.** It's built. It's
   correct. It costs a UI panel, not new backend work. This is the
   cheapest, most-overdue win available.
3. **Write down, in one file, what a "good enough" Tier 3 looks like to
   you** — and decide, explicitly, whether that bar is reachable with a
   local 3B model or whether this feature waits for a real API key. Don't
   let it stay ambiguous; it's been debugged twice this session already.
4. **CRUD parity for locations/organizations/lore/scenes.** Named as a gap
   before this session started; still a gap. Mechanically identical to what
   characters already have.
5. **Confidence-flagged extraction.** This is the real fix for the
   comedy-script problem you raised, not more exclusion rules — every
   exclusion I've added (Norse, "Constant") only covers what's already been
   seen. Flagging low-confidence entities for your confirmation, the same
   way coreference and entity-typing already degrade honestly, generalizes
   to genres nobody's tested yet.
6. **Get a real automated test file into this repo.** Even a single
   `test_app.py` covering the five reconciliation fixes and the canon
   checks would mean the next round of changes doesn't have to re-derive
   correctness from scratch by hand.
7. **Decide what "multi-user" needs to mean.** Login exists. Ownership
   doesn't. If this is ever used by more than you, that gap needs a real
   decision, not just more identity plumbing.

---

## 6. Is this doomed? My honest opinion.

**No — but it is not yet the app you said you'd be proud of either, and I
want to be direct about exactly why, not just reassuring.**

The architecture is sound. One typed-relationship table as the single source
of truth for the graph, the assistant, and the canon checks has held up
through a genuinely adversarial stress test — your own real, messy,
first-person manuscript — without needing to be redesigned once. Every real
bug found this session (and there were many, some severe) turned out to be
fixable *within* that architecture, verified, and non-regressive against the
existing seed data every single time. That's a healthy sign for a codebase,
not a doomed one. A doomed app usually reveals itself by needing a rewrite to
fix its third bug; this one didn't need one to fix its fifteenth.

What's real, and what I won't soften: this is still closer to a well-built
*engine* than a finished *product*. The intelligence layer (coref, relation
extraction, temporal reasoning, the knowledge graph, canon checking) is
genuinely good, deterministic, and now reasonably battle-tested. But the
things that make an app feel *finished* — full CRUD everywhere, an export
path, tests that don't depend on me re-verifying by hand each session,
confidence-aware extraction instead of silent over-trust, an actual answer
to what happens with more than one real user — are still mostly undone, and
several of them (tests, especially) are undone in a way that will cost more
the longer they stay that way.

The "generic shit" you were worried about a few rounds ago — that's been
substantially addressed. What's extracted and reconciled now is real,
specific, and traceable to your own text, not a flat co-occurrence blob.
What's NOT resolved is whether Tier 3 (the part meant to handle what
heuristics structurally can't) is actually good yet, because the only backend
available to test it against in this environment is a 3B local model that
needed two rounds of defensive fixes just to stop it from lying or losing
data. That's the honest, open question hanging over this app right now —
not "is the architecture broken," but "is the reasoning layer that's
supposed to close the remaining gaps actually capable enough yet, on the
only backend that's been testable here." I don't know that answer. Only
testing it against real material, or getting it in front of Claude with a
real key, will.
