"""Phase 3 — the Identity Engine, across applications.

*"Every entity receives a persistent identity. Identity survives renames.
Identity survives movement. Identity survives applications. Everything has one
identity."*

Phase 1 delivered the first three. These tests are about the fourth.
"""

import pytest

from creativeos_engine.events import EventKind
from creativeos_engine.graph import CreativeGraph, GraphError, ValidWindow


# -- external references --------------------------------------------------

def test_an_application_resolves_by_its_own_key(graph, space, cast):
    """FrameVault knows this person as user 7 and never stores a CreativeOS id."""
    kell = cast["kell"]
    graph.link_external(kell.id, "framevault", "user", 7)

    found = graph.resolve_external("framevault", "user", 7)
    assert found.id == kell.id


def test_three_applications_can_point_at_one_entity(graph, space, cast):
    """The whole problem Phase 3 exists to solve: FrameVault's user 7,
    FilmCrew's talent 12 and RightsForge's seller 4 are one person."""
    kell = cast["kell"]
    graph.link_external(kell.id, "framevault", "user", 7)
    graph.link_external(kell.id, "filmcrew", "talent", 12)
    graph.link_external(kell.id, "rightsforge", "seller", 4)

    assert graph.resolve_external("framevault", "user", 7).id == kell.id
    assert graph.resolve_external("filmcrew", "talent", 12).id == kell.id
    assert graph.resolve_external("rightsforge", "seller", 4).id == kell.id
    assert len(graph.external_refs_of(kell.id)) == 3


def test_resolving_an_unknown_key_returns_none(graph, space, cast):
    assert graph.resolve_external("framevault", "user", 999) is None


def test_the_same_key_cannot_be_repointed_silently(graph, space, cast):
    """Repointing would strand every fact recorded against the old entity, so
    it must be an explicit merge instead."""
    graph.link_external(cast["kell"].id, "framevault", "user", 7)
    with pytest.raises(GraphError) as e:
        graph.link_external(cast["sera"].id, "framevault", "user", 7)
    assert "already linked" in str(e.value)


def test_relinking_the_same_pair_is_harmless(graph, space, cast):
    graph.link_external(cast["kell"].id, "framevault", "user", 7)
    graph.link_external(cast["kell"].id, "framevault", "user", 7)
    assert len(graph.external_refs_of(cast["kell"].id)) == 1


def test_linking_emits_an_event(graph, space, cast):
    graph.link_external(cast["kell"].id, "framevault", "user", 7)
    linked = [e for e in graph.bus.history() if e.kind == EventKind.IDENTITY_LINKED]
    assert len(linked) == 1
    assert linked[0].payload["system"] == "framevault"


# -- merging --------------------------------------------------------------

def test_merging_makes_the_old_id_resolve_to_the_survivor(graph, space, cast):
    """An application still holding the old id is not broken by a merge it
    never heard about."""
    keep, dupe = cast["kell"], cast["sera"]
    graph.merge_entities(keep.id, dupe.id, reason="same person, two records")

    assert graph.canonical_id(dupe.id) == keep.id
    assert graph.get_entity(dupe.id).id == keep.id


def test_facts_from_both_sides_survive_a_merge(graph, space, cast):
    """Nothing is deleted and no assertion is rewritten — the survivor simply
    sees everything recorded against either id."""
    keep, dupe = cast["kell"], cast["sera"]
    graph.assert_attribute(keep.id, "rank", "second mate")
    graph.assert_attribute(dupe.id, "occupation", "navigator")

    graph.merge_entities(keep.id, dupe.id)

    state = graph.state_of(keep.id)
    assert state["rank"] == "second mate"
    assert state["occupation"] == "navigator"


def test_history_spans_the_merge(graph, space, cast):
    keep, dupe = cast["kell"], cast["sera"]
    graph.assert_attribute(keep.id, "rank", "second mate")
    graph.assert_attribute(dupe.id, "occupation", "navigator")
    graph.merge_entities(keep.id, dupe.id)

    assert len(graph.history_of(keep.id)) == 2


def test_relationships_from_both_sides_survive_a_merge(graph, space, cast):
    keep, dupe, harbour = cast["kell"], cast["sera"], cast["harbour"]
    graph.assert_relationship(dupe.id, "born_in", harbour.id)
    graph.merge_entities(keep.id, dupe.id)

    names = [other.name for _, other in graph.neighbors(keep.id)]
    assert "Ash Harbour" in names


def test_merging_can_reveal_a_contradiction(graph, space, cast):
    """Two records that looked fine apart can disagree once they are one thing —
    exactly the case the Verification Engine should catch."""
    keep, dupe = cast["kell"], cast["sera"]
    graph.assert_attribute(keep.id, "status", "alive", valid=ValidWindow(0, 500))
    graph.assert_attribute(dupe.id, "status", "dead", valid=ValidWindow(200, 600))
    assert graph.contradictions(space.id, entity_id=keep.id) == []

    graph.merge_entities(keep.id, dupe.id)

    found = graph.contradictions(space.id, entity_id=keep.id)
    assert len(found) == 1
    assert "alive" in found[0].describe() and "dead" in found[0].describe()


def test_external_keys_still_resolve_after_a_merge(graph, space, cast):
    keep, dupe = cast["kell"], cast["sera"]
    graph.link_external(dupe.id, "filmcrew", "talent", 12)
    graph.merge_entities(keep.id, dupe.id)

    assert graph.resolve_external("filmcrew", "talent", 12).id == keep.id


def test_merge_chains_resolve_all_the_way_through(graph, space, cast):
    """Merge B into A, then A into C: B must still resolve to C."""
    a, b, c = cast["kell"], cast["sera"], cast["harbour"]
    graph.merge_entities(a.id, b.id)
    graph.merge_entities(c.id, a.id)

    assert graph.canonical_id(b.id) == c.id
    assert graph.canonical_id(a.id) == c.id


def test_merging_an_entity_into_itself_is_rejected(graph, space, cast):
    with pytest.raises(GraphError):
        graph.merge_entities(cast["kell"].id, cast["kell"].id)


def test_merging_across_spaces_is_rejected(graph, space, cast):
    from creativeos_engine.domains import STORYATLAS
    other = graph.create_space("Another Show", domain="novel", pack=STORYATLAS)
    stranger = graph.create_entity(other.id, "character", "Outsider")
    with pytest.raises(GraphError):
        graph.merge_entities(cast["kell"].id, stranger.id)


def test_merging_emits_an_event(graph, space, cast):
    graph.merge_entities(cast["kell"].id, cast["sera"].id, reason="duplicate")
    merged = [e for e in graph.bus.history() if e.kind == EventKind.IDENTITY_MERGED]
    assert len(merged) == 1
    assert merged[0].payload["merged_id"] == cast["sera"].id
    assert merged[0].payload["reason"] == "duplicate"


# -- context and durability ----------------------------------------------

def test_context_reports_who_else_knows_about_this(graph, space, cast):
    kell = cast["kell"]
    graph.link_external(kell.id, "framevault", "user", 7)
    graph.link_external(kell.id, "filmcrew", "talent", 12)

    ctx = graph.context_of(kell.id)
    systems = {r.system for r in ctx["external_refs"]}
    assert systems == {"framevault", "filmcrew"}


def test_context_lists_ids_merged_into_this_one(graph, space, cast):
    graph.merge_entities(cast["kell"].id, cast["sera"].id)
    ctx = graph.context_of(cast["kell"].id)
    assert cast["sera"].id in ctx["merged_ids"]


def test_identity_survives_the_process(tmp_path):
    from creativeos_engine.domains import STORYATLAS

    db = tmp_path / "identity.db"
    with CreativeGraph(str(db)) as g:
        u = g.create_space("Persisted", domain="film", pack=STORYATLAS)
        keep = g.create_entity(u.id, "character", "Survivor")
        dupe = g.create_entity(u.id, "character", "Duplicate")
        g.link_external(keep.id, "framevault", "user", 7)
        g.merge_entities(keep.id, dupe.id)
        keep_id, dupe_id = keep.id, dupe.id

    with CreativeGraph(str(db)) as g:
        assert g.resolve_external("framevault", "user", 7).id == keep_id
        assert g.canonical_id(dupe_id) == keep_id


def test_rename_and_merge_together(graph, space, cast):
    """All four promises at once: the id survives a rename AND a merge, and the
    application's own key keeps working through both."""
    keep, dupe = cast["kell"], cast["sera"]
    graph.link_external(keep.id, "framevault", "user", 7)
    graph.assert_attribute(dupe.id, "occupation", "navigator")

    graph.merge_entities(keep.id, dupe.id)
    graph.rename_entity(keep.id, "Kell Varo-Ianto")

    resolved = graph.resolve_external("framevault", "user", 7)
    assert resolved.id == keep.id
    assert resolved.name == "Kell Varo-Ianto"
    assert graph.state_of(keep.id)["occupation"] == "navigator"
