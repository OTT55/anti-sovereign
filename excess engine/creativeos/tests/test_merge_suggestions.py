"""Finding duplicates, not just fixing them.

`merge_entities` could always repair a duplicate; nothing could find one. With
six applications writing into one graph, duplicates are a certainty.
"""

import pytest

from creativeos_engine.identity import IdentityRegistry


def _entities(graph, space, *names, kind="character"):
    return [graph.create_entity(space.id, kind, name) for name in names]


def test_a_legal_form_difference_is_suggested(graph, space):
    graph.declare_entity_type(space.id, "organization")
    _entities(graph, space, "Acme Corp", "Acme Corporation", kind="organization")

    suggestions = graph.suggest_merges(space.id)
    assert suggestions
    assert suggestions[0].keep.name == "Acme Corporation"   # the fuller name survives
    assert suggestions[0].merge.name == "Acme Corp"


def test_a_title_difference_is_suggested(graph, space):
    """FilmCrew records "Chancellor Aldric Vane"; RightsForge records
    "Aldric Vane". Nothing connected them."""
    _entities(graph, space, "Chancellor Aldric Vane", "Aldric Vane")
    suggestion = graph.suggest_merges(space.id)[0]
    assert suggestion.keep.name == "Chancellor Aldric Vane"
    assert suggestion.merge.name == "Aldric Vane"


def test_distinct_entities_are_not_suggested(graph, space):
    _entities(graph, space, "Aldric Vane", "Mara Sadel", "Tobin Reyes")
    assert graph.suggest_merges(space.id) == []


def test_entities_of_different_types_are_never_suggested(graph, space):
    """A person and an organisation sharing a name are two things."""
    graph.declare_entity_type(space.id, "organization")
    graph.create_entity(space.id, "character", "Meridian")
    graph.create_entity(space.id, "organization", "Meridian")
    assert graph.suggest_merges(space.id) == []


def test_names_differing_by_number_are_never_suggested(graph, space):
    """Merging "Production 12" into "Production 13" would attach one
    production's crew and contracts to another."""
    graph.declare_entity_type(space.id, "organization")
    _entities(graph, space, "Production 12", "Production 13", kind="organization")
    assert graph.suggest_merges(space.id) == []


def test_an_already_merged_entity_is_not_suggested_again(graph, space):
    a, b = _entities(graph, space, "Acme Corp", "Acme Corporation")
    graph.merge_entities(a.id, b.id, reason="same")
    assert graph.suggest_merges(space.id) == []


def test_suggestions_are_ranked_by_confidence(graph, space):
    _entities(graph, space, "Acme Corporation", "Acme Corp", "Acme Corporatoin")
    scores = [s.score for s in graph.suggest_merges(space.id)]
    assert scores == sorted(scores, reverse=True)


def test_nothing_is_merged_without_confirmation(graph, space):
    """Suggests only. A merge is consequential and hard to reverse."""
    a, b = _entities(graph, space, "Acme Corp", "Acme Corporation")
    graph.suggest_merges(space.id)

    assert graph.canonical_id(a.id) == a.id      # untouched
    assert graph.canonical_id(b.id) == b.id


def test_a_suggestion_explains_itself(graph, space):
    _entities(graph, space, "Acme Corp", "Acme Corporation")
    described = graph.suggest_merges(space.id)[0].describe()
    assert "Acme Corp" in described
    assert "character" in described


def test_a_higher_threshold_suggests_less(graph, space):
    _entities(graph, space, "Aldric Vane", "Aldrec Vane")
    assert len(graph.suggest_merges(space.id, threshold=0.7)) >= \
        len(graph.suggest_merges(space.id, threshold=0.95))


def test_each_pair_is_suggested_once(graph, space):
    _entities(graph, space, "Acme Corp", "Acme Corporation", "Acme Co")
    pairs = [tuple(sorted((s.keep.id, s.merge.id))) for s in graph.suggest_merges(space.id)]
    assert len(pairs) == len(set(pairs))


def test_suggestions_are_deterministic(graph, space):
    _entities(graph, space, "Acme Corp", "Acme Corporation", "Zenith Holdings")
    first = [s.describe() for s in graph.suggest_merges(space.id)]
    second = [s.describe() for s in graph.suggest_merges(space.id)]
    assert first == second


def test_an_empty_space_suggests_nothing(graph):
    empty = graph.create_space("Empty", domain="general")
    assert graph.suggest_merges(empty.id) == []


def test_the_registry_can_be_used_directly(graph, space):
    """Not only through the graph — the Identity Engine owns this."""
    entities = _entities(graph, space, "Acme Corp", "Acme Corporation")
    registry = IdentityRegistry(graph.store.conn)
    assert registry.suggest_merges(entities)
