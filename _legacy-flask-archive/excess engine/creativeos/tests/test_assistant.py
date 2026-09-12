"""Questions answered by traversal, with the method shown.

The three ideas lifted from Story Atlas's assistant: intent → traversal,
negative queries, and consequences rather than connections.
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
    hermit = graph.create_entity(space.id, "character", "The Hermit")

    graph.assert_attribute(aldric.id, "occupation", "navigator")
    graph.assert_attribute(aldric.id, "alive", "true", valid=ValidWindow(1102, 1147))
    graph.assert_relationship(aldric.id, "allied_with", mara.id)
    graph.assert_relationship(mara.id, "rival_of", tobin.id)
    return {"aldric": aldric, "mara": mara, "tobin": tobin, "hermit": hermit}


# -- intent recognition ----------------------------------------------------

def test_questions_map_to_the_right_intent(brain, space, world):
    cases = {
        "who is Aldric Vane": "profile",
        "who is connected to Aldric Vane": "connections",
        "who has never met Aldric Vane": "never-connected",
        "how are Aldric Vane and Tobin Reyes connected": "path",
        "what happens if Mara Sadel is removed": "impact",
        "what contradicts": "conflicts",
        "what is missing": "missing",
        "who matters most": "important",
    }
    for question, expected in cases.items():
        assert brain.ask(space.id, question).intent == expected, question


def test_a_negative_question_is_not_swallowed_by_the_positive_one(brain, space, world):
    """"never met" must be tested before "connected to", or it never fires."""
    assert brain.ask(space.id, "who has never met Aldric Vane").intent == "never-connected"


def test_an_unrecognised_question_says_so_and_offers_what_it_can_do(brain, space, world):
    answer = brain.ask(space.id, "write me a poem about the sea")
    assert answer.intent == "unknown"
    assert answer.items          # lists the shapes it can answer
    assert "guess" in answer.explain


# -- every answer shows its working ----------------------------------------

def test_every_answer_explains_its_method(brain, space, world):
    for question in ("who is Aldric Vane", "who is connected to Aldric Vane",
                     "who has never met Aldric Vane", "what is missing",
                     "who matters most", "what contradicts"):
        assert brain.ask(space.id, question).explain, question


def test_an_answer_renders_readably(brain, space, world):
    rendered = brain.ask(space.id, "who is connected to Aldric Vane").render()
    assert "Mara Sadel" in rendered
    assert "How:" in rendered


# -- the traversals --------------------------------------------------------

def test_a_profile_gathers_facts_and_relationships(brain, space, world):
    answer = brain.ask(space.id, "tell me about Aldric Vane")
    names = " ".join(i["name"] for i in answer.items)
    assert "navigator" in names
    assert "Mara Sadel" in names


def test_connections_reach_two_hops(brain, space, world):
    answer = brain.ask(space.id, "who is connected to Aldric Vane")
    assert {i["name"] for i in answer.items} >= {"Mara Sadel", "Tobin Reyes"}


def test_never_connected_finds_the_isolated_entity(brain, space, world):
    """The Hermit is connected to nobody — the useful answer here is absence."""
    answer = brain.ask(space.id, "who has never met Aldric Vane")
    assert "The Hermit" in {i["name"] for i in answer.items}
    assert "Mara Sadel" not in {i["name"] for i in answer.items}


def test_a_path_is_returned_with_its_route(brain, space, world):
    answer = brain.ask(space.id, "how are Aldric Vane and Tobin Reyes connected")
    assert answer.items
    assert "allied_with" in answer.items[0]["name"]


def test_unconnected_entities_are_reported_honestly(brain, space, world):
    answer = brain.ask(space.id, "how are Aldric Vane and The Hermit connected")
    assert "not connected" in answer.headline


def test_impact_reports_consequences_not_just_neighbours(brain, space, world):
    """"Loses a connection" is a fact; "would be left with nothing" is the
    consequence that matters."""
    answer = brain.ask(space.id, "what happens if Mara Sadel is removed")
    notes = " ".join(i["note"] for i in answer.items)
    assert "no connections at all" in notes


def test_conflicts_are_found(graph, brain, space, world):
    aldric = world["aldric"]
    graph.assert_attribute(aldric.id, "status", "alive", valid=ValidWindow(0, 400))
    graph.assert_attribute(aldric.id, "status", "dead", valid=ValidWindow(300, 600))
    answer = brain.ask(space.id, "what contradicts")
    assert answer.items


def test_a_year_question_uses_the_timeline(brain, space, world):
    answer = brain.ask(space.id, "who was alive in 1120")
    assert answer.intent == "timeline"
    assert "Aldric Vane" in {i["name"] for i in answer.items}


# -- subject resolution ----------------------------------------------------

def test_a_distinctive_surname_resolves_the_entity(brain, space, world):
    answer = brain.ask(space.id, "who is Sadel")
    assert answer.subject["name"] == "Mara Sadel"


def test_a_question_naming_nothing_known_says_so(brain, space, world):
    answer = brain.ask(space.id, "who is connected to Nobody At All")
    assert "could not find" in answer.headline


def test_answering_is_deterministic(brain, space, world):
    first = brain.ask(space.id, "who is connected to Aldric Vane").render()
    second = brain.ask(space.id, "who is connected to Aldric Vane").render()
    assert first == second
