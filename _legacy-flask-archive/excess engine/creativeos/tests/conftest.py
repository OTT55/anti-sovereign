import pytest

from creativeos_engine.domains import STORYATLAS
from creativeos_engine.graph import CreativeGraph


@pytest.fixture
def graph():
    g = CreativeGraph(":memory:")
    yield g
    g.close()


@pytest.fixture
def space(graph):
    """A space with StoryAtlas's vocabulary installed.

    The core ships no entity types at all, so a test space has to declare
    what it intends to store — that is the v2.0 boundary being exercised, not
    boilerplate.
    """
    return graph.create_space("The Sundered Coast", domain="film", pack=STORYATLAS)


@pytest.fixture
def cast(graph, space):
    """A small real scenario reused across tests: two characters, one city."""
    return {
        "kell": graph.create_entity(space.id, "character", "Kell Varo"),
        "sera": graph.create_entity(space.id, "character", "Sera Ianto"),
        "harbour": graph.create_entity(space.id, "location", "Ash Harbour"),
    }
