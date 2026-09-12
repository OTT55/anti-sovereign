"""Phase 6 — the AI Orchestrator.

The key property under test: with no provider registered this is fully
functional. It answers from the graph. A model improves the phrasing; it is not
load-bearing.

No real API is ever called here — providers are plain callables, which is the
whole point of routing by capability rather than importing an SDK.
"""

import pytest

from creativeos_engine.ai import AIOrchestrator
from creativeos_engine.graph import ValidWindow


@pytest.fixture
def ai(graph):
    return AIOrchestrator(graph)


@pytest.fixture
def world(graph, space):
    aldric = graph.create_entity(space.id, "character", "Aldric Vane")
    graph.assert_attribute(aldric.id, "occupation", "navigator",
                           source_kind="manuscript")
    graph.assert_attribute(aldric.id, "alive", "true", valid=ValidWindow(1102, 1147))
    return {"aldric": aldric}


# -- works with no model at all --------------------------------------------

def test_it_answers_with_no_provider_registered(ai, space, world):
    answer = ai.ask(space.id, "navigator")
    assert answer.mode == "extractive"
    assert "navigator" in answer.text
    assert "No AI provider is registered" in answer.note


def test_the_fallback_is_grounded_in_the_graph(ai, space, world):
    """Not a placeholder or an apology — a real answer, as true as the graph."""
    answer = ai.ask(space.id, "navigator")
    assert "Aldric Vane" in answer.text
    assert answer.cited_entities


def test_an_empty_space_says_so_plainly(graph, ai):
    empty = graph.create_space("Empty", domain="general")
    assert "Nothing relevant" in ai.ask(empty.id, "anything").text


# -- routing ---------------------------------------------------------------

def test_a_registered_provider_is_used(ai, space, world):
    ai.register("stub", lambda prompt, **kw: "Aldric was a navigator.")
    answer = ai.ask(space.id, "navigator")
    assert answer.mode == "generative"
    assert answer.provider == "stub"
    assert answer.text == "Aldric was a navigator."


def test_routing_is_by_capability_not_by_name(ai, space, world):
    ai.register("writer", lambda p, **kw: "written", capabilities=("generate",))
    ai.register("summariser", lambda p, **kw: "summarised", capabilities=("summarise",))

    assert ai.ask(space.id, "x", capability="summarise").text == "summarised"
    assert ai.ask(space.id, "x", capability="generate").text == "written"


def test_priority_decides_between_two_capable_providers(ai, space, world):
    ai.register("low", lambda p, **kw: "low", priority=1)
    ai.register("high", lambda p, **kw: "high", priority=10)
    assert ai.ask(space.id, "x").provider == "high"


def test_an_unmatched_capability_falls_back(ai, space, world):
    ai.register("writer", lambda p, **kw: "written", capabilities=("generate",))
    answer = ai.ask(space.id, "x", capability="translate")
    assert answer.mode == "extractive"


def test_a_provider_can_be_removed(ai, space, world):
    ai.register("stub", lambda p, **kw: "generated")
    ai.unregister("stub")
    assert ai.ask(space.id, "navigator").mode == "extractive"


# -- honest failure --------------------------------------------------------

def test_a_failing_provider_falls_back_and_says_why(ai, space, world):
    def explodes(prompt, **kw):
        raise RuntimeError("rate limited")

    ai.register("flaky", explodes)
    answer = ai.ask(space.id, "navigator")

    assert answer.mode == "extractive"
    assert "rate limited" in answer.note
    assert "Aldric Vane" in answer.text     # still answered


def test_a_provider_returning_nothing_falls_back(ai, space, world):
    ai.register("silent", lambda p, **kw: "   ")
    answer = ai.ask(space.id, "navigator")
    assert answer.mode == "extractive"
    assert "returned nothing" in answer.note


def test_the_mode_is_never_misreported(ai, space, world):
    """It never pretends a call happened."""
    ai.register("flaky", lambda p, **kw: (_ for _ in ()).throw(RuntimeError("down")))
    answer = ai.ask(space.id, "navigator")
    assert not answer.is_generative
    assert answer.summary()["mode"] == "extractive"


# -- prompts ---------------------------------------------------------------

def test_a_prompt_carries_the_assembled_context(ai, space, world):
    prompt, context = ai.build_prompt(space.id, "navigator")
    assert "Aldric Vane" in prompt
    assert "navigator" in prompt
    assert context.fragments


def test_the_prompt_forbids_going_beyond_the_context(ai, space, world):
    prompt, _ = ai.build_prompt(space.id, "navigator")
    assert "ONLY the context" in prompt


def test_a_prompt_warns_the_model_when_sources_disagree(graph, ai, space, world):
    """Otherwise a model silently picks one side of a conflict."""
    aldric = world["aldric"]
    graph.assert_attribute(aldric.id, "status", "alive", valid=ValidWindow(0, 400))
    graph.assert_attribute(aldric.id, "status", "dead", valid=ValidWindow(300, 600))

    prompt, context = ai.build_prompt(space.id, "Aldric")
    assert context.contradictions()
    assert "contradictory facts" in prompt


def test_the_extractive_answer_leads_with_the_disagreement(graph, ai, space, world):
    aldric = world["aldric"]
    graph.assert_attribute(aldric.id, "status", "alive", valid=ValidWindow(0, 400))
    graph.assert_attribute(aldric.id, "status", "dead", valid=ValidWindow(300, 600))

    answer = ai.ask(space.id, "Aldric")
    assert answer.text.startswith("The sources disagree:")


def test_a_budget_limits_what_goes_into_the_prompt(ai, space, world):
    """The budget governs how many *fragments* are selected, not the length of
    the rendered string — on a tiny budget the "omitted for space" notice can
    cost more than the fact it replaced."""
    _, small = ai.build_prompt(space.id, "navigator", budget=60)
    _, large = ai.build_prompt(space.id, "navigator", budget=5000)

    assert len(small.fragments) < len(large.fragments)
    assert small.dropped and not large.dropped


def test_the_provider_receives_options(ai, space, world):
    seen = {}

    def capture(prompt, **options):
        seen.update(options)
        return "ok"

    ai.register("stub", capture)
    ai.ask(space.id, "navigator", temperature=0.2, max_tokens=100)
    assert seen == {"temperature": 0.2, "max_tokens": 100}


def test_answering_is_deterministic_without_a_model(ai, space, world):
    assert ai.ask(space.id, "navigator").text == ai.ask(space.id, "navigator").text
