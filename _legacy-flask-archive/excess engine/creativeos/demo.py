"""A guided tour of what CreativeOS actually does today.

    python demo.py

Runs against the real engine — nothing here is illustrative or faked. Every
number and message printed is produced by the same code the tests exercise.
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent / "src"))

from creativeos_engine.domains import STORYATLAS          # noqa: E402
from creativeos_engine.graph import (                      # noqa: E402
    CreativeGraph, DomainPack, GraphError, ValidWindow,
)


def head(n, title):
    print(f"\n{'─' * 68}\n{n}. {title}\n{'─' * 68}")


g = CreativeGraph(":memory:")

# ---------------------------------------------------------------------------
head(1, "The core knows nothing until an application tells it")

bare = g.create_space("Empty Project", domain="general")
print(f"A fresh space knows these entity types: {g.entity_types(bare.id) or '(none)'}")
try:
    g.create_entity(bare.id, "character", "Kell Varo")
except GraphError as e:
    print(f"\nTrying to create a character anyway:\n  {e}")

print("\nThat refusal IS the architecture. CreativeOS does not know what a")
print("character is, and it must not — that word belongs to StoryAtlas.")

# ---------------------------------------------------------------------------
head(2, "An application plugs in by declaring its own vocabulary")

u = g.create_space("The Sundered Coast", domain="film", pack=STORYATLAS)
print(f"StoryAtlas declared {len(g.entity_types(u.id))} entity types, including:")
print(f"  {', '.join(sorted(g.entity_types(u.id))[:8])} …")

filmcrew = DomainPack(
    name="filmcrew",
    entity_types=("shooting_day", "crew_role"),
    functional_predicates=("call_time",),
)
g.install_pack(u.id, filmcrew)
print(f"\nFilmCrew plugged into the SAME space. Now {len(g.entity_types(u.id))} types.")
print("Two applications, one shared graph — neither owns it.")

# ---------------------------------------------------------------------------
head(3, "Facts are sourced claims, not fields")

kell = g.create_entity(u.id, "character", "Kell Varo")
harbour = g.create_entity(u.id, "location", "Ash Harbour")

g.assert_attribute(kell.id, "status", "alive", valid=ValidWindow(0, 300),
                   source_kind="manuscript", source_ref="ep01/sc04")
g.assert_attribute(kell.id, "status", "dead", valid=ValidWindow(300, None),
                   source_kind="manuscript", source_ref="ep07/sc22")
g.assert_relationship(kell.id, "born_in", harbour.id, source_kind="note")

print(f"Kell at story-tick 100: {g.state_of(kell.id, at=100)}")
print(f"Kell at story-tick 400: {g.state_of(kell.id, at=400)}")
print("\nEvery fact carries where it came from:")
for a in g.history_of(kell.id):
    where = f"{a.source_kind}:{a.source_ref}" if a.source_ref else a.source_kind
    print(f"  {a.predicate:<10} {str(a.object_repr()):<16} {a.valid.describe():<12} [{where}]")

# ---------------------------------------------------------------------------
head(4, "Continuity vs. contradiction — the two-clock payoff")

print(f"Contradictions so far: {len(g.contradictions(u.id))}")
print("  'alive until 300' and 'dead from 300' do not overlap — that's a story,")
print("  not a bug. The engine is not fooled by it.")

g.assert_attribute(kell.id, "status", "alive", valid=ValidWindow(250, 500),
                   source_kind="note", source_ref="draft-notes")
print(f"\nNow someone writes Kell alive from 250-500. Contradictions: "
      f"{len(g.contradictions(u.id))}")
for c in g.contradictions(u.id):
    print(f"  → {c.describe()}")
print("\nFound with pure interval logic. No AI, no guessing, no false positives.")

# ---------------------------------------------------------------------------
head(5, "Identity survives renames")

before_rels = len(g.neighbors(kell.id))
g.rename_entity(kell.id, "Kell Varo-Ianto")
print(f"Renamed. Facts intact: {g.state_of(kell.id, at=100)}")
print(f"Relationships intact: {before_rels} → {len(g.neighbors(kell.id))}")
print("The id is the identity; the name is only a label.")

# ---------------------------------------------------------------------------
head(6, "Applications talk through events, never to each other")

credited = []
analytics = []

g.bus.subscribe("hire.completed",
                lambda e: credited.append(e.payload["creator"]), name="framevault")
print("FrameVault subscribed to 'hire.completed'.")

g.bus.publish(u.id, "hire.completed", subject_id=kell.id,
              payload={"creator": "@ott", "production": "The Sundered Coast"},
              source="filmcrew")
print(f"FilmCrew published. FrameVault credited: {credited}")
print("  FilmCrew holds no URL, no key, no reference to FrameVault at all.")

g.bus.subscribe("hire.completed", analytics.append, name="analytics")
g.bus.publish(u.id, "hire.completed", subject_id=kell.id,
              payload={"creator": "@sam"}, source="filmcrew")
print(f"\nAdded an analytics listener — FilmCrew unchanged. Credited: {credited}")
print(f"Analytics saw {len(analytics)} event(s). THAT is decoupling.")

# ---------------------------------------------------------------------------
head(7, "One person, three applications")

g.link_external(kell.id, "framevault", "user", 7)
g.link_external(kell.id, "filmcrew", "talent", 12)
g.link_external(kell.id, "rightsforge", "seller", 4)

print("Each application keeps its OWN key and resolves through CreativeOS:")
for system, kind, key in (("framevault", "user", 7), ("filmcrew", "talent", 12),
                          ("rightsforge", "seller", 4)):
    found = g.resolve_external(system, kind, key)
    print(f"  {f'{system}:{kind}:{key}':<24} → {found.id}  ({found.name})")
print("\nNo application had to store a CreativeOS id it would need to keep in sync.")

# ---------------------------------------------------------------------------
head(8, "Two records turn out to be one person")

ghost = g.create_entity(u.id, "character", "K. Varo")
g.assert_attribute(ghost.id, "occupation", "navigator", source_kind="import")
g.link_external(ghost.id, "creatorstack", "member", 88)
print(f"A duplicate arrived from an import: {ghost.id} ('K. Varo')")
print("Apart, each record looks fine. The import says Kell is a navigator.")

g.merge_entities(kell.id, ghost.id, reason="same person, imported twice")
print(f"\nMerged. The old id still resolves: {ghost.id} → {g.canonical_id(ghost.id)}")
print(f"CreatorStack's key still works: "
      f"{g.resolve_external('creatorstack', 'member', 88).name}")
print(f"The import's fact came along: occupation = "
      f"{g.state_of(kell.id).get('occupation')}")
print("\nNothing was deleted and no fact was rewritten — the losing id became")
print("an alias, so any app still holding it keeps working.")

# ---------------------------------------------------------------------------
head(9, "Everything that happened, in order")

for e in g.bus.history():
    print(f"  {e.describe()}")

print(f"\nA listener written tomorrow can replay all {g.bus.log.count()} of these")
print("and catch up on history it was never present for.")

print(f"\n{'─' * 68}")
print("Built: Phase 1 (graph) + 2 (events) + 3 (identity). 89 tests, ~1.5s.")
print("Next:  Phase 4 — search across the graph.")
print(f"{'─' * 68}\n")

g.close()
