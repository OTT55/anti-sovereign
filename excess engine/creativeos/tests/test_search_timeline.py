"""An unbounded fact makes no claim about *when*.

Regression for a bug that made timeline search useless: any entity with a single
undated fact matched every window, so "who was alive in the year 1000?" returned
a character born in 1102.
"""

import pytest

from creativeos_engine.graph import ValidWindow
from creativeos_engine.search import SearchEngine


@pytest.fixture
def search(graph):
    return SearchEngine(graph)


def test_an_undated_fact_does_not_place_an_entity_in_time(graph, search, space):
    aldric = graph.create_entity(space.id, "character", "Aldric Vane")
    graph.assert_attribute(aldric.id, "occupation", "navigator")  # unbounded

    assert search.during(space.id, start=1000, end=1001) == []


def test_a_dated_fact_places_an_entity_only_in_its_own_window(graph, search, space):
    aldric = graph.create_entity(space.id, "character", "Aldric Vane")
    graph.assert_attribute(aldric.id, "alive", "true", valid=ValidWindow(1102, 1147))

    assert [h.entity.name for h in search.during(space.id, 1120, 1121)] == ["Aldric Vane"]
    assert search.during(space.id, 1000, 1001) == []
    assert search.during(space.id, 1200, 1201) == []


def test_timeline_search_can_filter_by_predicate(graph, search, space):
    aldric = graph.create_entity(space.id, "character", "Aldric Vane")
    graph.assert_attribute(aldric.id, "alive", "true", valid=ValidWindow(1102, 1147))
    graph.assert_attribute(aldric.id, "rank", "captain", valid=ValidWindow(1130, 1140))

    assert [h.entity.name for h in search.during(space.id, 1135, 1136, predicate="rank")] \
        == ["Aldric Vane"]
    assert search.during(space.id, 1145, 1146, predicate="rank") == []


def test_an_open_ended_window_still_counts_as_dated(graph, search, space):
    """"From 1147 onwards" is a real temporal claim even with no end."""
    tobin = graph.create_entity(space.id, "character", "Tobin Reyes")
    graph.assert_attribute(tobin.id, "status", "exiled", valid=ValidWindow(1147, None))

    assert [h.entity.name for h in search.during(space.id, 1200, 1201)] == ["Tobin Reyes"]
    assert search.during(space.id, 1100, 1101) == []
