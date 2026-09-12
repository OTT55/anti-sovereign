"""StoryAtlas writing into the CreativeOS graph — the layering, end to end.

Skipped if the CreativeOS engine is not importable; StoryAtlas's comprehension
does not depend on it, only this bridge does.
"""

import sys
from pathlib import Path

import pytest

# This app lives at creativeos/apps/storyatlas/, so the shared platform is three
# levels up. Resolved by *searching* rather than counting parents: a fixed
# `parents[n]` silently skipped this whole module when the app was moved under
# creativeos/, and a skipped test looks exactly like a passing one.
_CREATIVEOS_SRC = None
for _parent in Path(__file__).resolve().parents:
    _candidate = _parent / "src" / "creativeos_engine"
    if _candidate.is_dir():
        _CREATIVEOS_SRC = _candidate.parent
        break

if _CREATIVEOS_SRC is not None:
    sys.path.insert(0, str(_CREATIVEOS_SRC))

creativeos = pytest.importorskip("creativeos_engine.graph")

from storyatlas_engine import read                       # noqa: E402
from storyatlas_engine.bridge import commit, storyatlas_pack  # noqa: E402

DRAFT = (
    "Aldric Vane was born in the year 1102. "
    "Aldric Vane died in the year 1147. "
    "Mara Sadel was born in the year 1110. "
    "Mara Sadel died in the year 1150."
)


@pytest.fixture
def graph():
    g = creativeos.CreativeGraph(":memory:")
    yield g
    g.close()


@pytest.fixture
def space(graph):
    return graph.create_space("Meridian", domain="film", pack=storyatlas_pack())


def test_a_reading_becomes_entities_and_facts(graph, space):
    result = commit(read(DRAFT), graph, space.id)
    assert result["entities"] >= 2
    assert result["lifespans"] == 2


def test_characters_land_as_graph_entities(graph, space):
    commit(read(DRAFT), graph, space.id)
    names = {e.name for e in graph.find_entities(space.id, kind="character")}
    assert "Aldric Vane" in names
    assert "Mara Sadel" in names


def test_a_lifespan_becomes_a_bounded_assertion(graph, space):
    """StoryAtlas knows a death bounds a life; CreativeOS stores that as a
    valid-time window and can then verify against it."""
    commit(read(DRAFT), graph, space.id)
    aldric = graph.find_entities(space.id, name="Aldric Vane")[0]

    during = graph.state_of(aldric.id, at=1120)
    after = graph.state_of(aldric.id, at=1200)

    assert during.get("alive") == "true"   # inside the lifespan
    assert "alive" not in after            # the window closed at death
    assert "alive" not in graph.state_of(aldric.id, at=1050)  # before birth


def test_every_fact_cites_the_sentence_it_came_from(graph, space):
    commit(read(DRAFT), graph, space.id)
    aldric = graph.find_entities(space.id, name="Aldric Vane")[0]
    history = graph.history_of(aldric.id)
    assert history
    assert all(a.source_kind == "manuscript" for a in history)
    assert any(a.source_ref for a in history)


def test_unconfirmed_readings_are_held_back(graph, space):
    """A draft is not evidence until a human confirms the engine read it right."""
    reading = read("Aldric Vane was born in the year 1102. He was crowned at the age of thirty.")
    result = commit(reading, graph, space.id)
    assert result["held_for_confirmation"] == len(reading.questions)
    assert reading.questions


def test_the_core_still_refuses_undeclared_vocabulary(graph):
    """The v2.0 boundary holds: without StoryAtlas's pack, CreativeOS does not
    know what a character is."""
    bare = graph.create_space("Untyped", domain="general")
    with pytest.raises(creativeos.GraphError):
        graph.create_entity(bare.id, "character", "Nobody")
