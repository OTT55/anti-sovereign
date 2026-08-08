"""Phase 9 — the Intelligence Engine.

The constitution's six questions: what exists, what changed, what is connected,
what matters, what is missing, what happens next.
"""

import pytest

from creativeos_engine.graph import ValidWindow
from creativeos_engine.intelligence import IntelligenceEngine


@pytest.fixture
def brain(graph):
    return IntelligenceEngine(graph)


@pytest.fixture
def world(graph, space):
    aldric = graph.create_entity(space.id, "character", "Aldric Vane")
    mara = graph.create_entity(space.id, "character", "Mara Sadel")
    tobin = graph.create_entity(space.id, "character", "Tobin Reyes")
    harbour = graph.create_entity(space.id, "location", "Ash Harbour")

    for e in (aldric, mara, tobin):
        graph.assert_attribute(e.id, "occupation", "officer")
    graph.assert_attribute(aldric.id, "birth_year", "1102")
    graph.assert_attribute(mara.id, "birth_year", "1110")
    graph.assert_relationship(aldric.id, "allied_with", mara.id)
    graph.assert_relationship(mara.id, "rival_of", tobin.id)
    graph.assert_relationship(aldric.id, "born_in", harbour.id)
    return {"aldric": aldric, "mara": mara, "tobin": tobin, "harbour": harbour}


# -- what exists -----------------------------------------------------------

def test_what_exists_counts_by_kind(brain, space, world):
    exists = brain.what_exists(space.id)
    assert exists["total"] == 4
    assert exists["by_kind"]["character"] == 3
    assert exists["by_kind"]["location"] == 1


# -- what changed ----------------------------------------------------------

def test_what_changed_reads_the_event_log(brain, space, world):
    changed = brain.what_changed(space.id)
    assert changed
    assert any(e.kind == "entity.created" for e in changed)


def test_what_changed_can_resume_from_a_cursor(graph, brain, space, world):
    cursor = graph.bus.log.latest_sequence()
    graph.create_entity(space.id, "character", "Newcomer")
    changed = brain.what_changed(space.id, since=cursor)
    assert all(e.sequence > cursor for e in changed)


# -- what is connected -----------------------------------------------------

def test_what_is_connected_reaches_indirectly(brain, world):
    names = {h.entity.name for h in brain.what_is_connected(world["aldric"].id, depth=2)}
    assert "Tobin Reyes" in names


# -- what matters ----------------------------------------------------------

def test_what_matters_puts_the_well_connected_above_the_peripheral(brain, space, world):
    """Aldric and Mara each have two connections, two facts, and orphan someone
    if removed — they are genuinely tied, and both outrank the leaves."""
    ranked = dict(brain.what_matters(space.id))
    assert ranked["Aldric Vane"] == ranked["Mara Sadel"]
    assert ranked["Aldric Vane"] > ranked["Ash Harbour"]
    assert ranked["Mara Sadel"] > ranked["Ash Harbour"]


def test_a_genuine_hub_ranks_first(graph, brain, space):
    """One entity everything else hangs off should come top outright."""
    hub = graph.create_entity(space.id, "character", "The Chancellor")
    graph.assert_attribute(hub.id, "rank", "chancellor")
    for name in ("A", "B", "C", "D"):
        spoke = graph.create_entity(space.id, "character", name)
        graph.assert_relationship(hub.id, "knows", spoke.id)

    assert brain.what_matters(space.id)[0][0] == "The Chancellor"


def test_what_matters_scores_everything(brain, space, world):
    ranked = dict(brain.what_matters(space.id))
    assert set(ranked) == {"Aldric Vane", "Mara Sadel", "Tobin Reyes", "Ash Harbour"}
    assert all(0.0 <= v <= 1.0 for v in ranked.values())


def test_an_isolated_entity_matters_least(graph, brain, space, world):
    graph.create_entity(space.id, "character", "Nobody")
    ranked = brain.what_matters(space.id)
    assert ranked[-1][0] == "Nobody"


def test_an_empty_space_ranks_nothing(graph, brain):
    empty = graph.create_space("Empty", domain="general")
    assert brain.what_matters(empty.id) == []


# -- what is missing -------------------------------------------------------

def test_what_is_missing_finds_the_incomplete_record(brain, space, world):
    """Aldric and Mara have birth years; Tobin does not."""
    gaps = brain.what_is_missing(space.id)
    assert any(g.entity.name == "Tobin Reyes" and g.missing == "birth_year"
               for g in gaps)


# -- what happens next -----------------------------------------------------

def test_contradictions_are_recommended_before_gaps(graph, brain, space, world):
    """An unresolved conflict makes every answer drawn from those facts
    unreliable, so it outranks anything merely absent."""
    aldric = world["aldric"]
    graph.assert_attribute(aldric.id, "status", "alive", valid=ValidWindow(0, 400))
    graph.assert_attribute(aldric.id, "status", "dead", valid=ValidWindow(300, 600))

    recommendations = brain.what_happens_next(space.id)
    assert recommendations
    assert recommendations[0].startswith("Resolve the conflict")


def test_recommendations_are_actionable_sentences(brain, space, world):
    for rec in brain.what_happens_next(space.id):
        assert len(rec) > 10
        assert rec[0].isupper()


# -- the briefing ----------------------------------------------------------

def test_a_briefing_answers_all_six_questions(brain, space, world):
    b = brain.brief(space.id)
    assert b.exists["total"] == 4
    assert b.changed
    assert b.matters
    assert b.next_up is not None
    assert b.verdict is not None


def test_a_briefing_renders_readably(brain, space, world):
    rendered = brain.brief(space.id).render()
    assert "What matters" in rendered
    assert "Mara Sadel" in rendered


def test_a_briefing_summarises_numerically(brain, space, world):
    summary = brain.brief(space.id).summary()
    assert summary["entities"] == 4
    assert "Mara Sadel" in summary["key_entities"]


def test_a_briefing_surfaces_problems(graph, brain, space, world):
    aldric = world["aldric"]
    graph.assert_attribute(aldric.id, "status", "alive", valid=ValidWindow(0, 400))
    graph.assert_attribute(aldric.id, "status", "dead", valid=ValidWindow(300, 600))

    rendered = brain.brief(space.id).render()
    assert "needs attention" in rendered


def test_intelligence_is_deterministic(brain, space, world):
    assert brain.brief(space.id).render() == brain.brief(space.id).render()
