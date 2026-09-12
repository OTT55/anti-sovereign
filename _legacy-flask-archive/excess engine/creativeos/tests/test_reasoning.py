"""Phase 8 — the Reasoning Engine.

Search answers "what is connected to X". Reasoning answers "what follows from
X", which needs facts combined that no single record contains.
"""

import pytest

from creativeos_engine.reasoning import ReasoningEngine


@pytest.fixture
def reason(graph):
    return ReasoningEngine(graph)


@pytest.fixture
def world(graph, space):
    aldric = graph.create_entity(space.id, "character", "Aldric Vane")
    mara = graph.create_entity(space.id, "character", "Mara Sadel")
    tobin = graph.create_entity(space.id, "character", "Tobin Reyes")
    graph.assert_relationship(aldric.id, "allied_with", mara.id)
    graph.assert_relationship(mara.id, "rival_of", tobin.id)
    return {"aldric": aldric, "mara": mara, "tobin": tobin}


# -- paths -----------------------------------------------------------------

def test_a_path_is_found_between_indirectly_connected_entities(reason, world):
    paths = reason.paths_between(world["aldric"].id, world["tobin"].id)
    assert paths
    assert paths[0].length == 2


def test_a_path_explains_itself(reason, world):
    """The route is the explanation — "are they connected" is not the answer."""
    path = reason.paths_between(world["aldric"].id, world["tobin"].id)[0]
    described = path.describe()
    assert "Aldric Vane" in described
    assert "allied_with" in described
    assert "Tobin Reyes" in described


def test_shortest_paths_come_first(graph, reason, space, world):
    graph.assert_relationship(world["aldric"].id, "knows", world["tobin"].id)
    paths = reason.paths_between(world["aldric"].id, world["tobin"].id)
    assert paths[0].length == 1


def test_unconnected_entities_have_no_path(graph, reason, space, world):
    stranger = graph.create_entity(space.id, "character", "Outsider")
    assert reason.paths_between(world["aldric"].id, stranger.id) == []


def test_depth_limits_how_far_reasoning_will_reach(reason, world):
    assert reason.paths_between(world["aldric"].id, world["tobin"].id, max_depth=1) == []


# -- implications ----------------------------------------------------------

def test_a_transitive_chain_implies_an_unasserted_fact(graph, reason, space):
    """A part_of B, B part_of C, therefore A part_of C — nobody said so."""
    squad = graph.create_entity(space.id, "organization", "Ash Squad")
    fleet = graph.create_entity(space.id, "organization", "Northern Fleet")
    navy = graph.create_entity(space.id, "organization", "The Navy")
    graph.assert_relationship(squad.id, "part_of", fleet.id)
    graph.assert_relationship(fleet.id, "part_of", navy.id)

    implied = reason.implications(space.id)
    assert any(i.subject.name == "Ash Squad" and i.target.name == "The Navy"
               for i in implied)


def test_a_symmetric_relationship_implies_its_reverse(reason, space, world):
    implied = reason.implications(space.id)
    assert any(i.subject.name == "Mara Sadel" and i.target.name == "Aldric Vane"
               and i.predicate == "allied_with" for i in implied)


def test_a_non_transitive_predicate_does_not_chain(graph, reason, space, world):
    """Mara rivals Tobin and Aldric allies Mara — Aldric does not therefore
    rival anyone. Transitivity is a property of the predicate, not the graph."""
    implied = reason.implications(space.id)
    assert not any(i.subject.name == "Aldric Vane" and i.predicate == "rival_of"
                   for i in implied)


def test_an_implication_carries_the_facts_it_came_from(graph, reason, space):
    squad = graph.create_entity(space.id, "organization", "Ash Squad")
    fleet = graph.create_entity(space.id, "organization", "Northern Fleet")
    navy = graph.create_entity(space.id, "organization", "The Navy")
    graph.assert_relationship(squad.id, "part_of", fleet.id)
    graph.assert_relationship(fleet.id, "part_of", navy.id)

    implied = next(i for i in reason.implications(space.id)
                   if i.subject.name == "Ash Squad" and i.target.name == "The Navy")
    assert len(implied.because) == 2


def test_inference_never_gains_certainty_it_never_had(graph, reason, space):
    """A chain is only as sure as its weakest step."""
    squad = graph.create_entity(space.id, "organization", "Ash Squad")
    fleet = graph.create_entity(space.id, "organization", "Northern Fleet")
    navy = graph.create_entity(space.id, "organization", "The Navy")
    graph.assert_relationship(squad.id, "part_of", fleet.id, confidence=0.8)
    graph.assert_relationship(fleet.id, "part_of", navy.id, confidence=0.5)

    implied = next(i for i in reason.implications(space.id)
                   if i.subject.name == "Ash Squad" and i.target.name == "The Navy")
    assert implied.confidence == pytest.approx(0.4)


def test_an_already_asserted_fact_is_not_reported_as_implied(graph, reason, space):
    a = graph.create_entity(space.id, "organization", "A")
    b = graph.create_entity(space.id, "organization", "B")
    c = graph.create_entity(space.id, "organization", "C")
    graph.assert_relationship(a.id, "part_of", b.id)
    graph.assert_relationship(b.id, "part_of", c.id)
    graph.assert_relationship(a.id, "part_of", c.id)   # stated outright

    implied = [i for i in reason.implications(space.id)
               if i.subject.name == "A" and i.target.name == "C"]
    assert implied == []


# -- impact ----------------------------------------------------------------

def test_impact_lists_what_depends_on_an_entity(reason, world):
    impact = reason.impact_of_removing(world["mara"].id)
    names = {e.name for e in impact.direct}
    assert names == {"Aldric Vane", "Tobin Reyes"}


def test_impact_identifies_who_would_be_left_isolated(reason, world):
    """Aldric's only connection is Mara, so removing Mara strands him."""
    impact = reason.impact_of_removing(world["mara"].id)
    assert {e.name for e in impact.orphaned} == {"Aldric Vane", "Tobin Reyes"}


def test_orphaning_someone_is_worse_than_merely_disconnecting_them(graph, reason, space, world):
    graph.assert_relationship(world["aldric"].id, "knows", world["tobin"].id)
    impact = reason.impact_of_removing(world["mara"].id)
    assert impact.orphaned == []
    assert impact.severity < 4


def test_impact_of_an_unknown_entity_is_none(reason, world):
    assert reason.impact_of_removing("ENT-NOPE") is None


def test_impact_summarises_plainly(reason, world):
    summary = reason.impact_of_removing(world["mara"].id).summary()
    assert summary["entity"] == "Mara Sadel"
    assert "Aldric Vane" in summary["direct"]


# -- gaps ------------------------------------------------------------------

def test_a_missing_field_its_peers_all_have_is_a_gap(graph, reason, space):
    for name in ("A", "B", "C"):
        e = graph.create_entity(space.id, "character", name)
        graph.assert_attribute(e.id, "birth_year", "1100")
    incomplete = graph.create_entity(space.id, "character", "D")
    graph.assert_attribute(incomplete.id, "rank", "captain")

    gaps = reason.gaps(space.id)
    assert any(g.entity.name == "D" and g.missing == "birth_year" for g in gaps)


def test_nothing_is_a_gap_if_no_peer_has_it(graph, reason, space):
    """If nobody records birth years, not recording one is not a hole."""
    for name in ("A", "B", "C"):
        e = graph.create_entity(space.id, "character", name)
        graph.assert_attribute(e.id, "rank", "captain")

    assert not any(g.missing == "birth_year" for g in reason.gaps(space.id))


def test_gaps_explain_why_they_are_gaps(graph, reason, space):
    for name in ("A", "B", "C"):
        e = graph.create_entity(space.id, "character", name)
        graph.assert_attribute(e.id, "birth_year", "1100")
    graph.create_entity(space.id, "character", "D")

    gap = next(g for g in reason.gaps(space.id) if g.entity.name == "D")
    assert "3 of 4" in gap.reason


def test_reasoning_is_deterministic(reason, space, world):
    first = [i.describe() for i in reason.implications(space.id)]
    second = [i.describe() for i in reason.implications(space.id)]
    assert first == second
