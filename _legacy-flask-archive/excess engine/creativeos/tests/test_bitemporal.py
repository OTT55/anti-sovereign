"""The two clocks: story time (when a fact holds in-space) and record time
(when the creator believed it). These tests are the reason the model is shaped
the way it is — if they pass, retcons and continuity are separable."""

from creativeos_engine.graph import ids
from creativeos_engine.graph import ValidWindow


def test_state_depends_on_where_you_stand_in_the_story(graph, cast):
    kell = cast["kell"].id
    graph.assert_attribute(kell, "status", "alive", valid=ValidWindow(0, 300))
    graph.assert_attribute(kell, "status", "dead", valid=ValidWindow(300, None))

    assert graph.state_of(kell, at=0)["status"] == "alive"
    assert graph.state_of(kell, at=299)["status"] == "alive"
    assert graph.state_of(kell, at=300)["status"] == "dead"
    assert graph.state_of(kell, at=5000)["status"] == "dead"


def test_a_fact_outside_the_window_simply_is_not_there(graph, cast):
    kell = cast["kell"].id
    graph.assert_attribute(kell, "title", "Harbourmaster", valid=ValidWindow(400, 500))
    assert graph.state_of(kell, at=399) == {}
    assert graph.state_of(kell, at=450) == {"title": "Harbourmaster"}
    assert graph.state_of(kell, at=500) == {}


def test_retraction_removes_a_fact_from_current_state(graph, cast):
    kell = cast["kell"].id
    a = graph.assert_attribute(kell, "occupation", "smuggler")
    assert graph.state_of(kell) == {"occupation": "smuggler"}

    assert graph.retract(a.id, reason="changed in rewrite") is True
    assert graph.state_of(kell) == {}


def test_retraction_preserves_the_record(graph, cast):
    """A retcon must remain auditable: what was believed, and why it changed."""
    kell = cast["kell"].id
    a = graph.assert_attribute(kell, "occupation", "smuggler")
    graph.retract(a.id, reason="changed in rewrite")

    history = graph.history_of(kell)
    assert len(history) == 1
    assert history[0].is_retracted
    assert history[0].retraction_reason == "changed in rewrite"
    assert history[0].object_value == "smuggler"


def test_as_of_recovers_what_was_believed_before_the_retcon(graph, cast):
    """The headline bitemporal capability: rewind record time, keep story time."""
    kell = cast["kell"].id
    a = graph.assert_attribute(kell, "allegiance", "the Coast Guild",
                               valid=ValidWindow(0, 1000))
    before_retcon = ids.now()

    graph.retract(a.id, reason="Guild written out of the series")
    graph.assert_attribute(kell, "allegiance", "the Free Ports", valid=ValidWindow(0, 1000))

    # Today's canon
    assert graph.state_of(kell, at=500)["allegiance"] == "the Free Ports"
    # Canon as it stood before the rewrite — same story moment, earlier belief
    assert graph.state_of(kell, at=500, as_of=before_retcon)["allegiance"] == "the Coast Guild"


def test_as_of_hides_facts_authored_later(graph, cast):
    kell = cast["kell"].id
    checkpoint = ids.now()
    graph.assert_attribute(kell, "species", "human")

    assert graph.state_of(kell) == {"species": "human"}
    assert graph.state_of(kell, as_of=checkpoint) == {}


def test_retracting_twice_is_reported_as_no_change(graph, cast):
    a = graph.assert_attribute(cast["kell"].id, "rank", "second mate")
    assert graph.retract(a.id) is True
    assert graph.retract(a.id) is False  # already retracted, nothing to close


def test_relationships_respect_story_time_too(graph, cast):
    kell, sera = cast["kell"].id, cast["sera"].id
    graph.assert_relationship(kell, "allied_with", sera, valid=ValidWindow(0, 200))
    graph.assert_relationship(kell, "enemy_of", sera, valid=ValidWindow(200, None))

    early = [a.predicate for a in graph.relationships_of(kell, at=100)]
    late = [a.predicate for a in graph.relationships_of(kell, at=400)]
    assert early == ["allied_with"]
    assert late == ["enemy_of"]


def test_history_is_ordered_oldest_first_and_keeps_everything(graph, cast):
    kell = cast["kell"].id
    first = graph.assert_attribute(kell, "status", "alive")
    graph.retract(first.id, reason="draft 2")
    second = graph.assert_attribute(kell, "status", "missing")

    history = graph.history_of(kell)
    assert [a.id for a in history] == [first.id, second.id]
    assert history[0].is_retracted and not history[1].is_retracted
