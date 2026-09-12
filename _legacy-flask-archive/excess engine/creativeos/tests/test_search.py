"""Phase 4 — the Search Engine.

Keyword, relationship, traversal and timeline retrieval over the graph.
"""

import pytest

from creativeos_engine.graph import ValidWindow
from creativeos_engine.search import SearchEngine, tokenize


@pytest.fixture
def world(graph, space):
    """A small cast with real facts and relationships to search over."""
    aldric = graph.create_entity(space.id, "character", "Aldric Vane")
    mara = graph.create_entity(space.id, "character", "Mara Sadel")
    tobin = graph.create_entity(space.id, "character", "Tobin Reyes")
    harbour = graph.create_entity(space.id, "location", "Ash Harbour")

    graph.assert_attribute(aldric.id, "occupation", "navigator")
    graph.assert_attribute(aldric.id, "alive", "true", valid=ValidWindow(1102, 1147))
    graph.assert_attribute(mara.id, "occupation", "chancellor")
    graph.assert_attribute(mara.id, "alive", "true", valid=ValidWindow(1110, 1150))
    graph.assert_relationship(aldric.id, "born_in", harbour.id)
    graph.assert_relationship(aldric.id, "allied_with", mara.id)
    graph.assert_relationship(mara.id, "rival_of", tobin.id)

    return {"aldric": aldric, "mara": mara, "tobin": tobin, "harbour": harbour}


@pytest.fixture
def search(graph):
    return SearchEngine(graph)


# -- keyword ---------------------------------------------------------------

def test_tokenize_drops_stopwords():
    assert "the" not in tokenize("The Order of the Broken Crown")
    assert "broken" in tokenize("The Order of the Broken Crown")


def test_an_entity_is_found_by_its_name(search, space, world):
    hits = search.keyword(space.id, "Aldric")
    assert hits
    assert hits[0].entity.id == world["aldric"].id


def test_an_entity_is_found_by_a_fact_about_it(search, space, world):
    """"navigator" appears nowhere in Aldric's name — only in his facts."""
    hits = search.keyword(space.id, "navigator")
    assert hits
    assert hits[0].entity.id == world["aldric"].id


def test_a_query_matching_nothing_returns_nothing(search, space, world):
    assert search.keyword(space.id, "zzzblorp") == []


def test_a_retracted_fact_stops_making_an_entity_findable(graph, search, space, world):
    a = graph.assert_attribute(world["tobin"].id, "occupation", "cartographer")
    assert search.keyword(space.id, "cartographer", rebuild=True)

    graph.retract(a.id, reason="wrong")
    assert search.keyword(space.id, "cartographer", rebuild=True) == []


# -- relationship ----------------------------------------------------------

def test_related_finds_direct_connections(search, space, world):
    names = {h.entity.name for h in search.related(space.id, world["aldric"].id)}
    assert "Mara Sadel" in names
    assert "Ash Harbour" in names


def test_related_can_filter_by_predicate(search, space, world):
    hits = search.related(space.id, world["aldric"].id, predicate="born_in")
    assert [h.entity.name for h in hits] == ["Ash Harbour"]


def test_a_relationship_hit_records_which_predicate_connected_it(search, space, world):
    hits = search.related(space.id, world["aldric"].id, predicate="allied_with")
    assert hits[0].via == "allied_with"


# -- traversal -------------------------------------------------------------

def test_traversal_reaches_indirect_connections(search, space, world):
    """Tobin is two hops from Aldric: Aldric → Mara → Tobin. No text query can
    answer this at any level of cleverness."""
    names = {h.entity.name for h in search.traverse(space.id, world["aldric"].id, depth=2)}
    assert "Tobin Reyes" in names


def test_depth_one_does_not_reach_two_hops(search, space, world):
    names = {h.entity.name for h in search.traverse(space.id, world["aldric"].id, depth=1)}
    assert "Tobin Reyes" not in names
    assert "Mara Sadel" in names


def test_a_nearer_connection_outranks_a_further_one(search, space, world):
    hits = search.traverse(space.id, world["aldric"].id, depth=2)
    by_name = {h.entity.name: h for h in hits}
    assert by_name["Mara Sadel"].score > by_name["Tobin Reyes"].score


def test_traversal_keeps_the_path_that_reached_each_hit(search, space, world):
    """A connection you cannot explain is not much use."""
    hits = search.traverse(space.id, world["aldric"].id, depth=2)
    tobin = next(h for h in hits if h.entity.name == "Tobin Reyes")
    assert tobin.path[0] == world["aldric"].id
    assert tobin.path[-1] == world["tobin"].id
    assert len(tobin.path) == 3


# -- timeline --------------------------------------------------------------

def test_during_finds_who_was_alive_in_a_window(search, space, world):
    names = {h.entity.name for h in search.during(space.id, start=1140, end=1141)}
    assert "Aldric Vane" in names   # 1102–1147
    assert "Mara Sadel" in names    # 1110–1150


def test_during_excludes_what_was_not_yet_true(search, space, world):
    names = {h.entity.name for h in search.during(space.id, start=1000, end=1001)}
    assert "Aldric Vane" not in names


# -- hybrid ----------------------------------------------------------------

def test_hybrid_combines_text_and_graph_proximity(search, space, world):
    hits = search.find(space.id, query="chancellor", near=world["aldric"].id, depth=1)
    assert hits
    assert hits[0].entity.name == "Mara Sadel"   # matches the word AND is adjacent


def test_hybrid_works_with_only_a_query(search, space, world):
    hits = search.find(space.id, query="navigator")
    assert hits[0].entity.name == "Aldric Vane"


def test_hybrid_works_with_only_proximity(search, space, world):
    hits = search.find(space.id, near=world["aldric"].id, depth=1)
    assert {h.entity.name for h in hits} == {"Mara Sadel", "Ash Harbour"}


def test_search_is_deterministic(search, space, world):
    first = [h.entity.id for h in search.find(space.id, query="chancellor navigator")]
    second = [h.entity.id for h in search.find(space.id, query="chancellor navigator")]
    assert first == second
