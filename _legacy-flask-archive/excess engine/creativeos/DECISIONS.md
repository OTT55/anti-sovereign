# CreativeOS Engine — Architecture Decisions

Format per decision: **Context → Decision → Why → Trade-off → What I rejected.**
Written for a non-coder to follow, because the point of writing them down is to
be able to defend them later.

---

## 0001 — The core ships no domain vocabulary

**Context.** The first version of the graph had a fixed list of entity types
baked into it: `CHARACTER`, `SCENE`, `MAGIC_SYSTEM`, `DIALOGUE`, and twenty
more. Constitution v1.0 made that correct — CreativeOS *was* the storytelling
intelligence engine. v2.0 changed the job: CreativeOS is now the platform
*beneath* StoryAtlas, and v2.0 states the rule twice — *"CreativeOS understands
entities. StoryAtlas understands kingdoms"* and *"Never mix them."*

**Decision.** Delete the fixed type list from the core. An entity's type is a
plain string that an application declares first, via a `DomainPack`. Creating an
entity of an undeclared type is an error. The creative vocabulary moved to
`domains/storyatlas.py`, which the core never imports.

**Why.** A boundary that is only written in a document gets crossed. This one is
mechanical: there is no way to quietly store a `scene` in the core, because the
core does not know the word and will refuse it. A test asserts the core package
exposes no creative names at all.

**Trade-off.** More setup — you cannot create an entity without declaring its
type, so every test and every application needs a pack. That is real friction,
accepted deliberately because the friction is the enforcement.

**What I rejected.** Keeping the enum and "just being disciplined" — the
previous version proves discipline alone fails, since the vocabulary had already
leaked. Also rejected: allowing any free-text type with no declaration, which
removes the friction but also removes the boundary, and lets two applications
silently fork `character` / `Character` / `char`.

---

## 0002 — Two clocks: valid time and record time

**Context.** A creator writing on Tuesday can assert a fact about the year 1147
of their world. Those are different clocks.

**Decision.** Every assertion carries a `ValidWindow` (a half-open `[start, end)`
interval on the described world's own clock) *and* a `recorded_at` timestamp on
the real-world clock. Retraction sets `retracted_at` rather than deleting.

**Why.** It is the only way to tell two questions apart that look identical:
"was this character alive at tick 300?" (valid time) versus "did the author
still believe that last Tuesday?" (record time). A contradiction is two live
assertions that disagree *while their valid windows overlap*. A retcon is the
author retracting one. Without both axes you cannot distinguish a continuity
bug from an intentional revision — and that distinction is the entire value.

**Trade-off.** Every read needs to decide which clock it is asking about, so
almost every query takes `at=` and `as_of=` parameters. More surface area to
learn.

**What I rejected.** A single "last write wins" model, which cannot answer
"what did we believe before the retcon?" — that would make the Memory Engine's
*"nothing is forgotten"* impossible. Also rejected: real calendar support in the
core (regnal years, multiple moons), because that bakes one world's cosmology
into every world's storage. Valid time is a plain integer tick; calendars are an
application's job.

---

## 0003 — Facts are asserted and retracted, never edited

**Context.** The obvious design is a row per entity with columns you update.

**Decision.** Entities carry identity only — id, type, name. Everything *about*
an entity is a separate `Assertion` row with its own source, confidence, and
validity. Nothing is ever updated except to mark it retracted.

**Why.** It makes provenance per-fact instead of per-record: "this came from the
manuscript at ep01/sc04, that came from a note, this third one from an import,
and we stopped believing the second one on Thursday." History, retcon tracking,
and future branching all fall out of an append-only log for free. Branching an
append-only log is natural; branching a mutable table is not.

**Trade-off.** Reading current state costs more than reading a row — you replay
assertions and pick winners. Fine at this scale, and the indexes cover it, but
it is a real cost that grows.

**What I rejected.** Mutable entity rows with a separate audit table. That
duplicates the truth in two places and they drift; the audit log becomes
decorative rather than authoritative.

---

## 0004 — Which predicates can contradict is the application's call

**Context.** Contradiction detection needs to know that a character has one
`status` at a time but may have many `trait`s.

**Decision.** Only predicates explicitly declared *functional* are eligible to
contradict. A space with none declared reports no contradictions rather than
guessing. The declarations ship in the application's `DomainPack`.

**Why.** Single-valued-ness is domain judgement, not universal truth —
`species` is single-valued in most fiction and deliberately not in some. Guessing
wrong in the strict direction cries wolf on a character who is simply allowed to
be both brave and reckless, and a checker that cries wolf gets switched off.
False positives are more expensive than misses here.

**Trade-off.** A space that forgets to declare its predicates silently gets
no contradiction checking. Mitigated by packs declaring them, and it is tested.

**What I rejected.** Inferring functionality from the data (if a predicate has
only ever had one value, assume single-valued) — that turns a sparse corpus into
a wrong rule, and the rule then changes under you as more data arrives.

---

## 0005 — No model calls in the graph core

**Context.** Nearly every part of the constitution could be implemented by
asking a language model.

**Decision.** The graph core contains no model calls, no network, no framework.
Contradiction detection is pure set logic over overlapping intervals.

**Why.** Every other engine queries this constantly, and the Verification Engine
needs answers that are *provably* right rather than plausible. A deterministic
floor is also testable in milliseconds — the 54 tests run in about a third of a
second, which is what makes iterating on it cheap. Constitution v2.0 puts model
routing in the AI Orchestrator, a separate engine, and says *"AI is
infrastructure, not product."*

**Trade-off.** Genuinely judgement-based checks ("does this power level break
the established magic system?") cannot be expressed here at all. They belong to
a later phase, layered on top.

**What I rejected.** An LLM-based contradiction checker as the primary
mechanism. It would be non-deterministic, slow, expensive per query, and
impossible to unit-test properly — a bad foundation for something everything
else depends on.

---

## 0006 — SQLite, and record time as ISO-8601 strings

**Context.** The graph needs to persist and to answer "as of last Tuesday."

**Decision.** Plain `sqlite3`, no ORM. Record-time timestamps are UTC ISO-8601
strings compared lexicographically.

**Why.** SQLite is a file, needs no server, and is fast enough by orders of
magnitude at this scale. String comparison works for time ordering *only*
because every timestamp is written by one function at a fixed UTC offset — same
format, same zone, so alphabetical order equals chronological order. This is
noted in `store.py` because any code writing timestamps another way would break
`as_of` queries silently.

**Trade-off.** The lexicographic trick is a landmine for a future contributor
who writes a timestamp by hand. Postgres becomes correct once spaces get
large or need concurrent writers — the store layer is isolated so it can be
swapped without touching engine code.

**What I rejected.** A graph database (Neo4j) — a separate server to run and
deploy for a graph that currently fits comfortably in a file; same
scale-triggered reasoning ContextCore documented. Also rejected: an ORM, which
would hide exactly the query behaviour that matters most here.

---

## 0007 — The event log is durable, and written before anyone is told

**Context.** Phase 2 needed a way for applications to talk without calling each
other. The simplest version is an in-memory list of callbacks.

**Decision.** Every event is written to an append-only SQLite table **first**,
and only then dispatched to subscribers. The log shares the graph's database
connection, so a graph write and the event announcing it land in the same file.

**Why.** The events that matter most are the ones in flight when something
breaks. If the process dies after the write, the event is on disk and whoever
missed it replays from their cursor; if it dies before, the event genuinely
never happened. The opposite order can announce something that was never
recorded, and there is no way to recover from that — a listener acted on a fact
the system has no memory of.

**Trade-off.** Every publish costs a disk write and a commit. Measurably slower
than an in-memory queue, and it makes the bus useless for high-frequency
ephemeral signals. Accepted: these are business events, not telemetry.

**What I rejected.** A message broker (Redis, RabbitMQ, Kafka) — a separate
server to run for something that currently has one process, and it would put the
event history somewhere the graph cannot join against. The same log can be
fronted by a broker later without subscribers changing. Also rejected: in-memory
only, which loses exactly the events worth having.

---

## 0008 — A failing subscriber does not fail the write

**Context.** If FrameVault's listener throws while handling `hire.completed`,
what happens to the hire?

**Decision.** The exception is caught, recorded as a `DeliveryFailure`, and the
remaining subscribers still run. The write is not rolled back and the publish
call does not raise.

**Why.** The event is already durably logged, which means the thing it describes
genuinely happened — a listener's bug cannot un-happen it. And if one listener
could abort dispatch, every listener would become a single point of failure for
every other one; the bus would then be *more* fragile than the direct HTTP calls
it replaced, which would defeat the entire purpose.

**Trade-off.** Failures are silent unless something inspects `bus.failures`. A
retry policy and a dead-letter queue are not built yet, so a listener that fails
has to catch up via `replay()` from its cursor.

**What I rejected.** Propagating the exception (couples every publisher to every
subscriber's reliability). Also rejected: rolling back the graph write, which
would mean a downstream listener can veto an upstream fact — exactly the tight
coupling v2.0 forbids, just inverted.

---

## 0009 — Sequence numbers order events, not timestamps

**Context.** Subscribers need to process events in order and know where they got
to.

**Decision.** A monotonic integer `sequence`, assigned by SQLite's
autoincrement, is the ordering authority and the replay cursor. Timestamps are
recorded but never used for ordering.

**Why.** Two events can easily share a timestamp, which makes time ambiguous as
an ordering key. Clocks also move backwards — NTP corrections, daylight saving
handled wrongly, a VM resuming — and an ordering that can go backwards silently
corrupts every cursor depending on it. An integer that only ever increases has
neither problem.

**Trade-off.** The sequence is per-database, so it does not order events across
two separate deployments. That becomes real if CreativeOS is ever sharded, and
would need a hybrid logical clock. Not a problem worth solving now.

**What I rejected.** Ordering by `occurred_at` (ambiguous and clock-dependent),
and UUIDv7-style sortable ids (solves ordering but still leaves the cursor
awkward, and sequence integers are far easier to read in a log).

---

## 0010 — Applications keep their own keys; CreativeOS maps them

**Context.** *"Identity survives applications"* means FrameVault's `user 7`,
FilmCrew's `talent 12` and RightsForge's `seller 4` must be knowably one person.
The obvious approach is to make every application store the CreativeOS entity id.

**Decision.** Applications keep their own keys and register them:
`(framevault, user, 7) -> ENT-9F3A`. Resolution is a lookup. A key already
pointing at a different entity cannot be silently repointed — that is an error
telling you to merge instead.

**Why.** Requiring every application to store a foreign id means every
application now has a synchronisation problem, and any that drifts is silently
wrong. Letting them keep the key they already have makes adoption nearly free:
an existing app adds one `link_external` call and changes nothing else. The
repointing ban exists because repointing strands every fact recorded against the
old entity — the data does not move, so the reference must not either.

**Trade-off.** An extra indirection on every cross-application lookup, and the
mapping table becomes something to maintain.

**What I rejected.** A shared global id every app must adopt (a migration for
each app and a sync bug waiting to happen), and matching entities by name, which
is wrong the moment two people share a name or one person changes theirs.

---

## 0011 — Merging aliases, it does not rewrite

**Context.** Two entities turn out to be the same thing. The obvious fix is to
repoint the loser's assertions at the winner and delete the loser.

**Decision.** The merged id becomes an **alias**. Nothing is deleted and not one
assertion is rewritten. The old id keeps resolving to the survivor forever, and
every read — state, history, relationships, contradictions — gathers across the
whole identity group.

**Why.** Rewriting assertions would violate the append-only rule that decision
0003 is built on, and it destroys the record of what was believed before the
merge. Aliasing also makes merges safe to perform on a graph other applications
already hold references into: an app still using the old id keeps working
instead of breaking on an id that no longer exists. A merge is a statement about
the world, not an edit to the record.

**Trade-off.** Every read now resolves through the alias chain and unions across
the group, so reads cost more and the code is harder to follow than a simple
lookup. Un-merging is also not implemented — the alias would have to be removed
and any facts asserted since the merge attributed to one side or the other,
which needs a policy nobody has asked for yet.

**What I rejected.** Rewriting and deleting (loses history, breaks outstanding
references, contradicts 0003). Also rejected: refusing merges entirely and
making applications deal with duplicates, which just moves an
ecosystem-wide problem into six separate codebases.

A deliberate consequence worth naming: merging can **create** contradictions.
Two records that each looked consistent alone can disagree once they are one
thing. That is correct — the conflict was always there and the graph was simply
unable to see it. There is a test for exactly this.
