"""Is there anything that *explains* this conflict?

Adapted from Story Atlas's canon engine: two opposing facts are only worth
flagging if nothing recorded could account for the change. A character who is
both ally and enemy is a plot, provided something happened in between.
"""

import pytest

from creativeos_engine.graph import ValidWindow
from creativeos_engine.verification import VerificationEngine


@pytest.fixture
def verify(graph):
    return VerificationEngine(graph)


@pytest.fixture
def aldric(graph, space):
    return graph.create_entity(space.id, "character", "Aldric Vane")


def _conflict(graph, entity):
    graph.assert_attribute(entity.id, "status", "loyal", valid=ValidWindow(0, 400))
    graph.assert_attribute(entity.id, "status", "traitor", valid=ValidWindow(300, 600))


def test_a_bare_contradiction_is_unexplained(graph, verify, space, aldric):
    _conflict(graph, aldric)
    assert verify.unexplained_contradictions(space.id)


def test_an_intervening_fact_explains_the_change(graph, verify, space, aldric):
    """Something happened in between — that is a plot, not a bug."""
    _conflict(graph, aldric)
    graph.assert_attribute(aldric.id, "betrayed_by", "the Council",
                           valid=ValidWindow(350, 360))

    explained = verify.explained_contradictions(space.id)
    assert explained
    contradiction, bridges = explained[0]
    assert bridges
    assert bridges[0].predicate == "betrayed_by"
    assert verify.unexplained_contradictions(space.id) == []


def test_a_fact_outside_the_disputed_window_explains_nothing(graph, verify, space, aldric):
    _conflict(graph, aldric)
    graph.assert_attribute(aldric.id, "born_at", "Ash Harbour", valid=ValidWindow(900, 905))

    assert verify.unexplained_contradictions(space.id)


def test_a_timeless_fact_explains_nothing(graph, verify, space, aldric):
    """A fact with no window says nothing about *when* anything changed."""
    _conflict(graph, aldric)
    graph.assert_attribute(aldric.id, "species", "human")

    assert verify.unexplained_contradictions(space.id)


def test_another_value_of_the_same_thing_is_more_conflict_not_a_bridge(graph, verify, space, aldric):
    _conflict(graph, aldric)
    graph.assert_attribute(aldric.id, "status", "exiled", valid=ValidWindow(320, 380))

    assert verify.unexplained_contradictions(space.id)


def test_a_retracted_fact_cannot_bridge(graph, verify, space, aldric):
    _conflict(graph, aldric)
    bridge = graph.assert_attribute(aldric.id, "betrayed_by", "the Council",
                                    valid=ValidWindow(350, 360))
    assert verify.unexplained_contradictions(space.id) == []

    graph.retract(bridge.id, reason="removed from the draft")
    assert verify.unexplained_contradictions(space.id)


def test_a_clean_space_has_nothing_to_explain(graph, verify, space, aldric):
    graph.assert_attribute(aldric.id, "rank", "captain")
    assert verify.explained_contradictions(space.id) == []


def test_mitigation_is_deterministic(graph, verify, space, aldric):
    _conflict(graph, aldric)
    graph.assert_attribute(aldric.id, "betrayed_by", "the Council",
                           valid=ValidWindow(350, 360))
    first = [(c.describe(), [b.id for b in bs])
             for c, bs in verify.explained_contradictions(space.id)]
    second = [(c.describe(), [b.id for b in bs])
              for c, bs in verify.explained_contradictions(space.id)]
    assert first == second
