# CreativeOS Engine — Build Plan

Honest gap analysis against `CLAUDE.md` (Constitution v2.0), and the phase order
to close it. Each phase ships something real and independently testable.

> Rewritten for v2.0. The previous version measured against v1.0, where
> CreativeOS *was* the creative-intelligence engine. Under v2.0 CreativeOS is
> the platform beneath six applications, so most of what v1.0 called a
> CreativeOS engine is now an **application** engine. The old analysis is kept
> in git history; `CONSTITUTION-v1.0-superseded.md` holds the old constitution.

## The headline finding

Two separate things exist today and neither is CreativeOS:

1. **`companies/creativeos/`** — three real, working Flask apps (FrameVault,
   FilmCrew, RightsForge), verified end to end. Under v2.0 these are **domain
   applications**, correctly so. But they integrate by calling each other's HTTP
   endpoints directly (`/api/credit`, `/api/authenticate`), which v2.0
   explicitly forbids: *"Applications communicate only through events. No tight
   coupling."* And FrameVault is doing double duty as both an application and
   the de-facto identity provider for the others — that second job belongs to
   the CreativeOS Identity and Platform engines, not to an application.

2. **`excess engine/creativeos/`** (this folder) — the Creative Knowledge Graph
   core. Real and tested. It covers the substrate that the Knowledge, Identity,
   Graph, Memory and Verification engines are built out of.

So the platform layer between them — the thing v2.0 is actually about — is
almost entirely unbuilt. There is no event bus, no shared graph the applications
write into, no context assembly, no AI orchestration.

## Per-engine inventory

| v2.0 core engine | Current state |
|---|---|
| **Knowledge** | **Partial.** Everything is an entity with a declared type, and every fact is a sourced assertion. Real and tested. Missing: ingestion of actual documents/files into entities — nothing turns a script or a contract into knowledge yet. |
| **Identity** | **Real.** Persistent `ENT-…` ids surviving renames, external-reference mapping so each application keeps its own key, and merging by alias so an id is never invalidated. All four constitutional promises hold, plus `suggest_merges()` — it finds duplicate entities across applications and proposes them for confirmation, never merging on its own. Missing: un-merge. |
| **Graph** | **Real.** Relationships with direction, valid-time windows, provenance and history. This is the strongest piece. |
| **Memory** | **Partial.** Append-only assertions, retraction-not-deletion, full history per entity, bitemporal `as_of` queries. Missing: branches, and snapshots/versioning of files. |
| **Context** | **Real.** Assembly + budgeting by relevance × confidence × recency, contradictions exempt from the budget, provenance carried per fragment. Missing: cross-*application* assembly proper, which needs more than one app writing into the graph. |
| **Reasoning** | **Real.** Paths, implications, impact analysis and gap detection, each carrying the facts it was derived from. Missing: reasoning over valid time (what followed from what, when). |
| **Verification** | **Real.** Contradictions, evidence with independent-source weighting, ambiguity, relationship validity against lifespans, and an explainable certainty score. |
| **Intelligence** | **Real.** All six questions answered, plus a rendered briefing. Missing: proactive/scheduled scanning — it answers when asked rather than watching. |
| **Search** | **Real.** Keyword (TF-IDF), relationship, traversal and timeline retrieval, plus a hybrid rank. Missing: semantic/embedding search, which needs a model. |
| **Event** | **Real.** Durable append-only log, publish/subscribe with wildcard and prefix patterns, replay from a cursor, isolated subscriber failures. Every graph write emits. Missing: cross-process transport, retry/dead-letter, and porting the existing apps onto it. |
| **Workflow** | **Real.** Event-driven rules, conditions, bounded cascades, loop prevention, full run audit. Missing: scheduling and background execution — rules fire synchronously on events. |
| **AI Orchestrator** | **Real.** Capability routing, context-built prompts, honest extractive fallback, fully functional with no model configured. Missing: streaming, token accounting, and any actual provider binding — deliberately, since none is wanted. |
| **Storage** | **Real.** Content-addressed blobs, version chains, entity attachment, duplicate detection. Missing: an object-store backend — blobs live in SQLite, which is right at this scale and wrong at video scale. |
| **Platform** | **Real.** Accounts, organizations, membership, roles, permissions, space access, notifications over the bus. Deliberately absent: password hashing, sessions, billing — a library call and a payment provider, not architecture. |

## Phase order

Rationale: the graph exists, so the next scarce thing is the **seam** — a way
for applications to put knowledge into the graph and hear about each other's
changes without calling each other directly. Event and Identity come before the
smart engines (Reasoning, Intelligence), because those are worthless over a
graph nothing writes into.

**Phase 1 — Creative Knowledge Graph core.** ← *built, 54 tests, see `DECISIONS.md`*
Entities, sourced assertions, bitemporality, relationships, history,
deterministic contradiction detection, and a domain-type registry that keeps
application vocabulary out of the core.

**Phase 2 — Event Engine.** ← *built, 69 tests total, see `DECISIONS.md` 0007–0009*
Durable append-only event log with publish/subscribe and replay. Every graph
write emits an event, so *"everything emits events"* is literally true and
tested. Applications publish their own kinds (`hire.completed`,
`asset.licensed`) and know nothing about who listens — a test adds a third
listener without touching the publisher, which is the real proof the coupling is
gone. Failing subscribers are isolated, ordering is by monotonic sequence rather
than clock, and the log is written before dispatch so nothing in flight is lost.
Deterministic, in-process, no network and no model calls.

**Phase 3 — Identity Engine, cross-application.** ← *built, 89 tests total, see `DECISIONS.md` 0010–0011*
External-reference mapping (`framevault:user:7` ↔ `filmcrew:talent:12` ↔ one
entity id) plus merging, so *"identity survives applications"* is now true
rather than aspirational. Applications keep their own keys; a key cannot be
silently repointed. Merges alias rather than rewrite: nothing is deleted, no
assertion is touched, the old id resolves forever, and every read gathers across
the identity group. Merging can newly reveal a contradiction that was always
there — tested.

**Phase 4 — Search Engine.** Hybrid retrieval over the graph: keyword first
(deterministic, no dependency), then relationship/graph traversal, then semantic
once embeddings exist. ContextCore's TF-IDF work is directly reusable here.

**Phase 5 — Context Engine.** ← *built, 123 tests total*
Assembles knowledge for a question and fits it to a character budget, scoring by
**relevance × confidence × recency** — multiplied, not added, so a fact nobody
is confident in cannot buy its way in by being very relevant. Contradictions
bypass the budget entirely: a context that omits the fact its own contents
disagree produces confident answers built on a conflict nobody saw. Retracted
facts never reach it. Renders grouped by entity and says how much it dropped.

**Phase 6 — AI Orchestrator.** ← *built, 241 tests total. Kept for last on purpose.*
Provider routing **by capability** rather than by name, prompts built only from
the Context Engine (so a model sees the same budgeted, provenance-carrying
context everything else does, and is warned when sources disagree), and an
honest fallback. The property that matters: **with no provider registered this
is fully functional** — it answers from the graph, labelled `extractive`. A
model improves the phrasing; it is not load-bearing. It never fabricates and
never pretends a call happened.

**Phase 7 — Verification Engine, completed.** ← *built, 141 tests total*
Evidence tracking that weights **independent sources** (two documents agreeing
gives 0.84; the same document quoted twice stays 0.6 — treating those alike is
how a rumour becomes a fact), ambiguity detection for names meaning more than
one entity, relationship validation against lifespans (serving under a commander
a century after they died), and a single `certainty` number set by the weakest
load-bearing claim and capped hard by any contradiction.

**Phase 8 — Reasoning Engine.** ← *built, 161 tests total*
Paths (the route *is* the explanation), implications from declared transitive
and symmetric predicates (A part_of B, B part_of C ⇒ A part_of C, with
confidence multiplied so a chain never gains certainty it never had), impact
analysis (what breaks if this is removed — orphans weighted double), and gap
detection (what *comparable* entities have and this one lacks). Transitivity is
declared per predicate, not assumed: `part_of` chains, `rival_of` does not.

**Phase 9 — Intelligence Engine.** ← *built, 178 tests total*
The constitution's six questions, each delegating to the engine that owns the
capability. Contains almost no logic of its own, deliberately — a coordinator
that starts computing things has quietly become a second implementation. The
one genuinely new idea is **what matters**: importance is not a property of any
record, so it is computed from connections + knowledge + impact, normalised and
weighted. Recommendations put contradictions first, because an unresolved
conflict makes every answer drawn from those facts unreliable.

**Phase 10 — Storage, Workflow, Platform.** ← *built, 223 tests total*
**Storage**: content-addressed blobs (SHA-256 of the bytes) with a walkable
version chain — changing a file gives it a new identity rather than silently
replacing the old one, which is what makes "this fact came from that draft"
mean anything. **Workflow**: event-driven rules with bounded cascade depth and
loop prevention, since a rule's action writes to the graph, which emits an
event, which can match another rule. **Platform**: accounts, organizations,
membership, roles and permissions — the job currently trapped inside FrameVault.
Password hashing, sessions and billing are deliberately absent; `authenticate()`
takes a verifier callback so credentials never pass through the platform.

## Open boundary questions

Two pieces of v1.0 vocabulary survive in the core and should be settled before
they harden:

- **`Space`** — *settled.* It was `Universe`, which was narrative vocabulary in a
  layer that must have none: RightsForge has clients, FilmCrew has productions,
  and neither has a universe. `Workspace` collides with OTT Studio's Workspace
  Engine and `Domain` with the Domain Engine, so the name chosen was `Space`:
  neutral, no collision, and it reads correctly for every application. Ids are
  now `SPC-…`.

- **The `domains/` packs** (currently just StoryAtlas) live in this repo as
  reference implementations that exercise the registry. Each should move into
  its own application repo as that application is built.

## Status

**All ten phases are built and tested — 241 tests**, all deterministic, no
model calls, no network. `DECISIONS.md` records the architectural decisions and
their trade-offs; `README.md` shows how to run it, and `demo.py` is a guided
tour for reading the engine without reading the code.

Every engine in Constitution v2.0 now exists. The honest remaining work is
listed per-engine in the inventory above — chiefly: porting the
`companies/creativeos/` apps onto the Event Engine, semantic search, branches in
Memory, and proactive scanning in Intelligence. Phase 6 (AI Orchestrator) is
deferred deliberately — OTT's direction is no API calls, and every engine so far
has been answerable deterministically, so the orchestrator is built last as the
seam for when a model is genuinely wanted.

This engine work does not modify the `companies/creativeos/` apps — they keep
running as they are. Later phases port their integration onto the event bus and
the graph rather than editing them in place.

Working rhythm, same as `companies/cinematic ott/`: one phase at a time, run its
tests, explain the result in plain language, then stop and wait.
