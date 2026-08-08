"""`context_of` is the shape Engine 12 will consume, so it gets its own test:
one call must answer the constitution's design-philosophy questions."""

from creativeos_engine.graph import ValidWindow


def test_context_answers_the_constitutions_questions(graph, space, cast):
    kell, sera, harbour = cast["kell"].id, cast["sera"].id, cast["harbour"].id

    graph.assert_attribute(kell, "occupation", "harbour pilot",
                           source_kind="manuscript", source_ref="ep01/sc04")
    graph.assert_attribute(kell, "status", "alive", valid=ValidWindow(0, 300))
    graph.assert_relationship(kell, "born_in", harbour, source_kind="note")
    graph.assert_relationship(kell, "sails_with", sera, valid=ValidWindow(0, 200))
    dropped = graph.assert_attribute(kell, "rank", "second mate", source_kind="note")
    graph.retract(dropped.id, reason="cut in draft 3")

    ctx = graph.context_of(kell, at=100)

    # What exists
    assert ctx["entity"].name == "Kell Varo"
    # What it means
    assert ctx["state"] == {"occupation": "harbour pilot", "status": "alive"}
    # How it is connected
    assert sorted(a.predicate for a, _ in ctx["relationships"]) == ["born_in", "sails_with"]
    assert {other.name for _, other in ctx["relationships"]} == {"Ash Harbour", "Sera Ianto"}
    # What changed
    assert ctx["history_count"] == 5
    assert ctx["retracted_count"] == 1
    # Where it came from ("authored" is the default for the un-sourced status fact)
    assert ctx["sources"] == ["authored", "manuscript", "note"]
    # What contradicts it
    assert ctx["contradictions"] == []


def test_context_surfaces_contradictions_when_they_exist(graph, cast):
    kell = cast["kell"].id
    graph.assert_attribute(kell, "status", "alive", valid=ValidWindow(0, 400))
    graph.assert_attribute(kell, "status", "dead", valid=ValidWindow(300, 600))

    ctx = graph.context_of(kell)
    assert len(ctx["contradictions"]) == 1


def test_context_moves_with_story_time(graph, cast):
    kell, sera = cast["kell"].id, cast["sera"].id
    graph.assert_relationship(kell, "allied_with", sera, valid=ValidWindow(0, 200))
    graph.assert_relationship(kell, "enemy_of", sera, valid=ValidWindow(200, None))

    early = graph.context_of(kell, at=100)
    late = graph.context_of(kell, at=300)
    assert [a.predicate for a, _ in early["relationships"]] == ["allied_with"]
    assert [a.predicate for a, _ in late["relationships"]] == ["enemy_of"]


def test_context_of_a_bare_entity_is_empty_but_valid(graph, cast):
    ctx = graph.context_of(cast["sera"].id)
    assert ctx["state"] == {}
    assert ctx["relationships"] == []
    assert ctx["history_count"] == 0
    assert ctx["contradictions"] == []
