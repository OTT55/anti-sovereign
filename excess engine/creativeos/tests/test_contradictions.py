"""Contradiction detection. The false-positive tests matter as much as the
positive ones — a canon checker that cries wolf gets switched off, and then it
protects nothing."""

from creativeos_engine.graph import ValidWindow


def test_overlapping_conflicting_facts_are_flagged(graph, space, cast):
    kell = cast["kell"].id
    graph.assert_attribute(kell, "status", "alive", valid=ValidWindow(0, 400))
    graph.assert_attribute(kell, "status", "dead", valid=ValidWindow(300, 600))

    found = graph.contradictions(space.id)
    assert len(found) == 1
    assert found[0].predicate == "status"
    assert found[0].subject_id == kell
    assert "alive" in found[0].describe() and "dead" in found[0].describe()


def test_sequential_facts_are_not_a_contradiction(graph, space, cast):
    """Dying at tick 300 is a plot point, not a continuity error."""
    kell = cast["kell"].id
    graph.assert_attribute(kell, "status", "alive", valid=ValidWindow(0, 300))
    graph.assert_attribute(kell, "status", "dead", valid=ValidWindow(300, 600))
    assert graph.contradictions(space.id) == []


def test_non_functional_predicates_are_never_flagged(graph, space, cast):
    """A character is allowed to be both brave and reckless at once."""
    kell = cast["kell"].id
    graph.assert_attribute(kell, "trait", "brave")
    graph.assert_attribute(kell, "trait", "reckless")
    assert graph.contradictions(space.id) == []


def test_identical_values_are_not_a_contradiction(graph, space, cast):
    kell = cast["kell"].id
    graph.assert_attribute(kell, "species", "human", source_ref="ep01")
    graph.assert_attribute(kell, "species", "human", source_ref="ep07")
    assert graph.contradictions(space.id) == []


def test_retracting_one_side_resolves_the_contradiction(graph, space, cast):
    kell = cast["kell"].id
    graph.assert_attribute(kell, "status", "alive", valid=ValidWindow(0, 400))
    bad = graph.assert_attribute(kell, "status", "dead", valid=ValidWindow(300, 600))
    assert len(graph.contradictions(space.id)) == 1

    graph.retract(bad.id, reason="continuity fix")
    assert graph.contradictions(space.id) == []


def test_different_characters_do_not_contradict_each_other(graph, space, cast):
    graph.assert_attribute(cast["kell"].id, "status", "alive")
    graph.assert_attribute(cast["sera"].id, "status", "dead")
    assert graph.contradictions(space.id) == []


def test_contradictions_can_be_scoped_to_one_entity(graph, space, cast):
    graph.assert_attribute(cast["kell"].id, "status", "alive")
    graph.assert_attribute(cast["kell"].id, "status", "dead")
    graph.assert_attribute(cast["sera"].id, "rank", "captain")
    graph.assert_attribute(cast["sera"].id, "rank", "deckhand")

    assert len(graph.contradictions(space.id)) == 2
    assert len(graph.contradictions(space.id, entity_id=cast["kell"].id)) == 1


def test_conflicting_functional_relationships_are_flagged(graph, space, cast):
    """Functional predicates work on relationships too — one `location` at a
    time, whether it points at a literal or at a place entity."""
    other_port = graph.create_entity(space.id, "location", "Grey Reach")
    graph.assert_relationship(cast["kell"].id, "location", cast["harbour"].id,
                              valid=ValidWindow(0, 100))
    graph.assert_relationship(cast["kell"].id, "location", other_port.id,
                              valid=ValidWindow(50, 150))

    found = graph.contradictions(space.id)
    assert len(found) == 1
    assert found[0].predicate == "location"


def test_declaring_a_predicate_functional_starts_flagging_it(graph, space, cast):
    kell = cast["kell"].id
    graph.assert_attribute(kell, "eye_colour", "grey")
    graph.assert_attribute(kell, "eye_colour", "green")
    assert graph.contradictions(space.id) == []

    graph.declare_functional(space.id, "eye_colour")
    assert len(graph.contradictions(space.id)) == 1


def test_undeclaring_stops_flagging(graph, space, cast):
    kell = cast["kell"].id
    graph.assert_attribute(kell, "status", "alive")
    graph.assert_attribute(kell, "status", "dead")
    assert len(graph.contradictions(space.id)) == 1

    graph.undeclare_functional(space.id, "status")
    assert graph.contradictions(space.id) == []


def test_as_of_shows_a_contradiction_that_used_to_exist(graph, space, cast):
    from creativeos_engine.graph import ids

    kell = cast["kell"].id
    graph.assert_attribute(kell, "status", "alive", valid=ValidWindow(0, 400))
    bad = graph.assert_attribute(kell, "status", "dead", valid=ValidWindow(300, 600))
    while_broken = ids.now()
    graph.retract(bad.id, reason="continuity fix")

    assert graph.contradictions(space.id) == []
    assert len(graph.contradictions(space.id, as_of=while_broken)) == 1
