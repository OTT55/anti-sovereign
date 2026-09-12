"""Identity, assertions, and state — the everyday path."""

import pytest

from creativeos_engine.domains import STORYATLAS
from creativeos_engine.graph import (
    AssertionKind, CreativeGraph, GraphError, ValidWindow,
)


def test_entities_get_readable_scoped_ids(graph, space):
    kell = graph.create_entity(space.id, "character", "Kell Varo")
    assert kell.id.startswith("ENT-")
    assert kell.space_id == space.id
    assert graph.get_entity(kell.id).name == "Kell Varo"


def test_entity_in_unknown_space_is_rejected(graph):
    with pytest.raises(GraphError):
        graph.create_entity("SPC-DOESNOTEXIST", "character", "Nobody")


def test_attribute_assertion_shows_up_in_state(graph, cast):
    graph.assert_attribute(cast["kell"].id, "occupation", "harbour pilot")
    assert graph.state_of(cast["kell"].id) == {"occupation": "harbour pilot"}


def test_later_assertion_overrides_earlier_one_for_same_predicate(graph, cast):
    graph.assert_attribute(cast["kell"].id, "occupation", "harbour pilot")
    graph.assert_attribute(cast["kell"].id, "occupation", "smuggler")
    assert graph.state_of(cast["kell"].id)["occupation"] == "smuggler"


def test_multi_valued_predicates_are_not_collapsed_in_history(graph, cast):
    """`trait` isn't functional, so both survive in the record even though
    state_of() can only show one value per predicate."""
    graph.assert_attribute(cast["kell"].id, "trait", "brave")
    graph.assert_attribute(cast["kell"].id, "trait", "reckless")
    traits = [a.object_value for a in graph.history_of(cast["kell"].id)
              if a.predicate == "trait"]
    assert sorted(traits) == ["brave", "reckless"]


def test_relationship_connects_two_entities_both_ways(graph, cast):
    graph.assert_relationship(cast["kell"].id, "sails_with", cast["sera"].id)

    outbound = graph.relationships_of(cast["kell"].id, direction="out")
    assert [a.predicate for a in outbound] == ["sails_with"]
    assert outbound[0].kind == AssertionKind.RELATIONSHIP

    inbound = graph.relationships_of(cast["sera"].id, direction="in")
    assert [a.subject_id for a in inbound] == [cast["kell"].id]

    assert graph.relationships_of(cast["sera"].id, direction="out") == []


def test_neighbors_resolves_the_other_entity(graph, cast):
    graph.assert_relationship(cast["kell"].id, "born_in", cast["harbour"].id)
    pairs = graph.neighbors(cast["kell"].id)
    assert len(pairs) == 1
    assertion, other = pairs[0]
    assert assertion.predicate == "born_in"
    assert other.name == "Ash Harbour"


def test_relationship_to_unknown_entity_is_rejected(graph, cast):
    with pytest.raises(GraphError):
        graph.assert_relationship(cast["kell"].id, "knows", "ENT-NOPE")


def test_relationship_across_spaces_is_rejected(graph, space, cast):
    other_space = graph.create_space("A Different Show", domain="novel", pack=STORYATLAS)
    stranger = graph.create_entity(other_space.id, "character", "Outsider")
    with pytest.raises(GraphError):
        graph.assert_relationship(cast["kell"].id, "knows", stranger.id)


def test_provenance_is_recorded_on_every_assertion(graph, cast):
    a = graph.assert_attribute(
        cast["kell"].id, "status", "alive",
        source_kind="manuscript", source_ref="ep01/sc04", confidence=0.8,
    )
    stored = graph.history_of(cast["kell"].id)[0]
    assert stored.id == a.id
    assert (stored.source_kind, stored.source_ref) == ("manuscript", "ep01/sc04")
    assert stored.confidence == 0.8


def test_find_entities_filters_by_kind(graph, space, cast):
    characters = graph.find_entities(space.id, kind="character")
    assert sorted(e.name for e in characters) == ["Kell Varo", "Sera Ianto"]
    locations = graph.find_entities(space.id, kind="location")
    assert [e.name for e in locations] == ["Ash Harbour"]


def test_graph_persists_to_a_real_file(tmp_path):
    """A creative space outlives the process that created it — the
    constitution's "design for long-lived creative spaces" in practice."""
    db = tmp_path / "space.db"
    with CreativeGraph(str(db)) as g:
        u = g.create_space("Persisted", domain="game", pack=STORYATLAS)
        e = g.create_entity(u.id, "character", "Remembered")
        g.assert_attribute(e.id, "status", "alive", valid=ValidWindow(0, 100))
        entity_id, space_id = e.id, u.id

    with CreativeGraph(str(db)) as g:
        assert g.get_entity(entity_id).name == "Remembered"
        assert g.state_of(entity_id, at=50) == {"status": "alive"}
        assert len(g.find_entities(space_id)) == 1
