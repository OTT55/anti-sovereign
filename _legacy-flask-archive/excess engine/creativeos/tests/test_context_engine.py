"""Phase 5 — the Context Engine.

Assembling relevant knowledge and *budgeting* it. The budget is the hard part:
retrieval finds everything relevant, context decides what is worth the space.

(Phase 1's `context_of()` is covered separately in `test_context.py`.)
"""

import pytest

from creativeos_engine.context import ContextEngine
from creativeos_engine.graph import ValidWindow


@pytest.fixture
def ctx(graph):
    return ContextEngine(graph)


@pytest.fixture
def world(graph, space):
    aldric = graph.create_entity(space.id, "character", "Aldric Vane")
    mara = graph.create_entity(space.id, "character", "Mara Sadel")
    harbour = graph.create_entity(space.id, "location", "Ash Harbour")

    graph.assert_attribute(aldric.id, "occupation", "navigator",
                           source_kind="manuscript", source_ref="ep01/sc04")
    graph.assert_attribute(aldric.id, "alive", "true", valid=ValidWindow(1102, 1147))
    graph.assert_relationship(aldric.id, "born_in", harbour.id)
    graph.assert_relationship(aldric.id, "allied_with", mara.id)
    graph.assert_attribute(mara.id, "occupation", "chancellor")
    return {"aldric": aldric, "mara": mara, "harbour": harbour}


def test_context_gathers_facts_about_a_matched_entity(ctx, space, world):
    c = ctx.assemble(space.id, question="navigator")
    assert "Aldric Vane" in c.entities
    assert any("navigator" in f.text for f in c.fragments)


def test_context_includes_relationships_not_just_attributes(ctx, space, world):
    c = ctx.assemble(space.id, near=world["aldric"].id, depth=1)
    kinds = {f.kind for f in c.fragments}
    assert "relationship" in kinds


def test_valid_time_is_shown_on_dated_facts(ctx, space, world):
    c = ctx.assemble(space.id, question="alive")
    assert any("1102" in f.text for f in c.fragments)


def test_provenance_travels_with_each_fragment(ctx, space, world):
    c = ctx.assemble(space.id, question="navigator")
    assert any(f.source == "manuscript" for f in c.fragments)


# -- the budget ------------------------------------------------------------

def test_a_small_budget_drops_the_lowest_ranked_items(ctx, space, world):
    c = ctx.assemble(space.id, question="navigator chancellor", budget=80)
    assert c.dropped


def test_a_large_budget_drops_nothing(ctx, space, world):
    c = ctx.assemble(space.id, question="navigator chancellor", budget=100000)
    assert c.dropped == []


def test_the_summary_reports_what_was_left_out(ctx, space, world):
    c = ctx.assemble(space.id, question="navigator chancellor", budget=80)
    s = c.summary()
    assert s["dropped"] > 0
    assert s["budget"] == 80


def test_a_retracted_fact_never_reaches_the_context(graph, ctx, space, world):
    a = graph.assert_attribute(world["mara"].id, "occupation", "cartographer")
    assert any("cartographer" in f.text
               for f in ctx.assemble(space.id, question="cartographer").fragments)

    graph.retract(a.id, reason="wrong")
    c = ctx.assemble(space.id, question="cartographer")
    assert not any("cartographer" in f.text for f in c.fragments)


# -- contradictions bypass the budget --------------------------------------

def test_a_contradiction_is_always_included_however_tight_the_budget(graph, ctx, space, world):
    """A context that omits the fact its own contents disagree is worse than no
    context — it produces confident answers built on a conflict nobody saw."""
    aldric = world["aldric"]
    graph.assert_attribute(aldric.id, "status", "alive", valid=ValidWindow(0, 400))
    graph.assert_attribute(aldric.id, "status", "dead", valid=ValidWindow(300, 600))

    c = ctx.assemble(space.id, question="Aldric", budget=1)
    assert c.contradictions()
    assert any("CONFLICT" in f.text for f in c.fragments)


# -- rendering -------------------------------------------------------------

def test_render_groups_by_entity(ctx, space, world):
    rendered = ctx.assemble(space.id, question="navigator").render()
    assert "## Aldric Vane" in rendered
    assert "Question: navigator" in rendered


def test_render_says_when_things_were_omitted(ctx, space, world):
    rendered = ctx.assemble(space.id, question="navigator chancellor", budget=80).render()
    assert "omitted for space" in rendered


def test_assembly_is_deterministic(ctx, space, world):
    first = ctx.assemble(space.id, question="navigator").render()
    second = ctx.assemble(space.id, question="navigator").render()
    assert first == second
