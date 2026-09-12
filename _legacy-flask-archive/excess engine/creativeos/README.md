# CreativeOS Engine

The intelligence platform beneath the creative application ecosystem — not any
one of the applications. Governed by `CLAUDE.md` (Constitution v2.0).

CreativeOS owns **universal** intelligence: entities, identity, relationships,
history, context, evidence. Applications (StoryAtlas, RightsForge, FilmCrew,
FrameVault, CreatorStack, OTT Studio) own **domain** intelligence: kingdoms,
licenses, call sheets. The two are never mixed, and here that rule is enforced
by code rather than by good intentions.

## What is built

**All fourteen engines of Constitution v2.0 exist.** 241 tests, deterministic —
no model calls, no network, no framework.

| Engine | What it does |
|---|---|
| **Knowledge / Graph** | Entities, sourced assertions, relationships, bitemporality |
| **Identity** | Ids surviving renames, moves and applications; merge by alias |
| **Memory** | Append-only history, retraction not deletion, `as_of` queries |
| **Event** | Durable log, publish/subscribe, replay from a cursor |
| **Search** | Keyword (TF-IDF), relationship, traversal, timeline, hybrid |
| **Context** | Assembly + budgeting by relevance × confidence × recency |
| **Verification** | Contradictions, evidence, ambiguity, certainty |
| **Reasoning** | Paths, implications, impact, gaps |
| **Intelligence** | The six questions, plus a rendered briefing |
| **Workflow** | Event-driven rules, bounded cascades, audit trail |
| **Storage** | Content-addressed blobs, version chains |
| **Platform** | Accounts, organizations, roles, permissions |
| **AI Orchestrator** | Capability routing — *fully functional with no model* |

Run `python demo.py` for a guided tour without reading the code.
`BUILD_PLAN.md` carries the honest per-engine gaps.

```
src/creativeos_engine/
  graph/          entities, assertions, bitemporality, contradictions
  events/         durable log + publish/subscribe/replay
  identity/       external references + merge aliases
  search/         TF-IDF index + four retrieval modes
  context/        assembly and budgeting
  verification/   evidence, ambiguity, relationship validity
  reasoning/      paths, implications, impact, gaps
  intelligence/   the coordinator
  workflow/       event-driven rules
  storage/        content-addressed blobs + version chains
  platform/       accounts, orgs, roles, permissions
  ai/             provider routing, honest extractive fallback
  domains/        StoryAtlas's vocabulary — NOT core, moves out later
demo.py           a guided tour of everything built
tests/            241 tests, deterministic, ~5s
```

### The four constitutional promises, as real methods

| Constitution | Method |
|---|---|
| Identity Engine — *identity survives renames* | `create_entity` / `rename_entity` |
| Graph Engine — *every relationship exists here* | `relationships_of` / `neighbors` |
| Memory Engine — *nothing is forgotten* | `history_of` (retractions kept) |
| Verification Engine — *detects contradictions* | `contradictions` (deterministic) |
| Context Engine — *assembles relevant information* | `context_of` |

## Try it

```bash
python -m pytest -q
```

```python
from creativeos_engine.domains import STORYATLAS
from creativeos_engine.graph import CreativeGraph, ValidWindow

g = CreativeGraph(":memory:")

# An application declares its vocabulary. The core ships none.
u = g.create_space("The Sundered Coast", domain="film", pack=STORYATLAS)

kell = g.create_entity(u.id, "character", "Kell Varo")
harbour = g.create_entity(u.id, "location", "Ash Harbour")

# Facts are sourced claims valid over a window of the world's own clock.
g.assert_attribute(kell.id, "status", "alive", valid=ValidWindow(0, 300),
                   source_kind="manuscript", source_ref="ep01/sc04")
g.assert_attribute(kell.id, "status", "dead", valid=ValidWindow(300, None))
g.assert_relationship(kell.id, "born_in", harbour.id, source_kind="note")

g.state_of(kell.id, at=100)     # {'status': 'alive'}
g.state_of(kell.id, at=400)     # {'status': 'dead'}
g.contradictions(u.id)          # [] — the windows don't overlap, that's continuity

# Now a real continuity bug:
g.assert_attribute(kell.id, "status", "alive", valid=ValidWindow(250, 500))
[c.describe() for c in g.contradictions(u.id)]
# ["status: 'dead' (from 300) vs 'alive' (250–500)"]
```

Renaming does not disturb anything, because the id is the identity:

```python
g.rename_entity(kell.id, "Kell Varo-Ianto")
g.state_of(kell.id)      # unchanged
g.neighbors(kell.id)     # unchanged
```

## The boundary, enforced

The core will refuse a type nobody declared:

```python
bare = g.create_space("Untyped", domain="general")
g.create_entity(bare.id, "character", "Nobody")
# GraphError: Entity type 'character' was never declared for this space.
#   Declared types: none yet. Install a DomainPack or call declare_entity_type()
#   first — CreativeOS ships no vocabulary of its own.
```

`tests/test_domain_boundary.py` asserts the core package exposes no creative
vocabulary at all, so the boundary cannot rot silently.

## Events: how applications stop calling each other

Today FilmCrew POSTs directly to FrameVault's `/api/credit`, so it must know
FrameVault's URL, service key, uptime and response shape. v2.0 forbids that:
*"Applications communicate only through events."*

```python
# FrameVault listens. It has no reference to FilmCrew.
g.bus.subscribe("hire.completed",
                lambda e: credit(e.payload["creator"]), name="framevault")

# FilmCrew publishes. It has no reference to FrameVault.
g.bus.publish(u.id, "hire.completed", subject_id=kell.id,
              payload={"creator": "@ott"}, source="filmcrew")
```

Adding a third listener needs no change to FilmCrew at all — that is the
practical test of whether the coupling is really gone.

Every graph write emits too, so the log is a complete record of what happened:

```python
for e in g.bus.history():
    print(e.describe())
# #1 space.created SPC-… (from creativeos.graph)
# #2 pack.installed   SPC-… (from creativeos.graph)
# #3 entity.created   ENT-… (from creativeos.graph)
# #4 assertion.added  ENT-… (from creativeos.graph)
```

An application added *later* catches up on everything it missed, which is what
makes the ecosystem reactive rather than merely decoupled:

```python
cursor = g.bus.replay(handler, kind="assertion.*")   # replays history
# ... later, resume from where it stopped
g.bus.replay(handler, since=cursor, kind="assertion.*")
```

Three guarantees worth knowing: the log is written **before** subscribers are
told (a crash mid-dispatch loses nothing), ordering is by monotonic `sequence`
rather than clock, and a subscriber that raises is recorded in `bus.failures`
without breaking the write or the other subscribers. Reasoning in `DECISIONS.md`
0007–0009.

## Identity: one person, many applications

FrameVault knows a person as `user 7`, FilmCrew as `talent 12`, RightsForge as
`seller 4`. Each keeps its own key — nobody has to store a CreativeOS id and
keep it in sync:

```python
g.link_external(kell.id, "framevault", "user", 7)
g.link_external(kell.id, "filmcrew", "talent", 12)

g.resolve_external("filmcrew", "talent", 12).id == kell.id   # True
```

When two records turn out to be one person, merging **aliases** rather than
rewrites. Nothing is deleted, no assertion is touched, and the losing id keeps
resolving forever — so an application still holding it is not broken by a merge
it never heard about:

```python
g.merge_entities(kell.id, duplicate.id, reason="imported twice")

g.canonical_id(duplicate.id) == kell.id     # old id still resolves
g.state_of(kell.id)["occupation"]           # the duplicate's facts came along
```

A deliberate consequence: merging can **reveal** a contradiction. Two records
that each looked consistent alone can disagree once they are one thing. That is
correct — the conflict was always there, the graph just couldn't see it.
Reasoning in `DECISIONS.md` 0010–0011.

## What is not built

Everything else. Honestly: Event, Reasoning, Intelligence, Search, Workflow, AI
Orchestrator, Storage and Platform do not exist; Context and Verification are
partial. `BUILD_PLAN.md` has the per-engine inventory and the phase order — the
next phase is the **Event Engine**, because the existing `companies/creativeos/`
apps currently integrate by calling each other's HTTP endpoints directly, which
Constitution v2.0 forbids.

## Relationship to `companies/creativeos/`

That folder holds three real, working applications (FrameVault, FilmCrew,
RightsForge). Under v2.0 they are domain applications and they keep running as
they are. This engine does not modify them; later phases port their integration
onto the event bus and the shared graph rather than editing them in place.
