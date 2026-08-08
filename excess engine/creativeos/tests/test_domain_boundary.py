"""The Constitution v2.0 boundary, enforced mechanically.

*"CreativeOS owns universal intelligence. Applications own domain intelligence.
Never mix them."* These tests are what stops that from being a slogan: the core
ships no vocabulary, and it refuses to store a type nobody declared.
"""

import pytest

from creativeos_engine.domains import STORYATLAS
from creativeos_engine.graph import DomainPack, GraphError, TypeError_, normalize_type


# -- the core ships no vocabulary of its own -----------------------------

def test_a_fresh_space_knows_no_entity_types(graph):
    """CreativeOS has no opinion about what exists until an application says."""
    bare = graph.create_space("Untyped", domain="general")
    assert graph.entity_types(bare.id) == set()


def test_creating_an_undeclared_type_is_rejected(graph):
    bare = graph.create_space("Untyped", domain="general")
    with pytest.raises(GraphError) as e:
        graph.create_entity(bare.id, "character", "Kell Varo")
    assert "never declared" in str(e.value)


def test_the_core_package_imports_no_domain_vocabulary():
    """If `graph` ever imports from `domains`, the boundary has been broken."""
    import creativeos_engine.graph as core

    source_names = dir(core)
    for leaked in ("CHARACTER", "SCENE", "MAGIC_SYSTEM", "EntityKind", "StoryWindow"):
        assert leaked not in source_names


# -- applications declare their own vocabulary ---------------------------

def test_installing_a_pack_declares_types_and_functional_predicates(graph):
    u = graph.create_space("Coast", domain="film", pack=STORYATLAS)
    assert "character" in graph.entity_types(u.id)
    assert "magic_system" in graph.entity_types(u.id)
    assert "status" in graph.store.functional_predicates(u.id)


def test_a_declared_type_can_then_be_created(graph):
    bare = graph.create_space("Untyped", domain="general")
    graph.declare_entity_type(bare.id, "character")
    kell = graph.create_entity(bare.id, "character", "Kell Varo")
    assert kell.kind == "character"


def test_two_packs_are_additive_on_one_space(graph):
    """A shared graph is the point: StoryAtlas and FilmCrew can both describe
    the same production without either owning it."""
    filmcrew = DomainPack(
        name="filmcrew",
        entity_types=("shooting_day", "crew_role"),
        functional_predicates=("call_time",),
    )
    u = graph.create_space("Coast", domain="film", pack=STORYATLAS)
    graph.install_pack(u.id, filmcrew)

    types = graph.entity_types(u.id)
    assert "character" in types      # StoryAtlas
    assert "shooting_day" in types   # FilmCrew
    assert "call_time" in graph.store.functional_predicates(u.id)


def test_type_names_are_normalized_so_spellings_cannot_fork(graph):
    bare = graph.create_space("Untyped", domain="general")
    graph.declare_entity_type(bare.id, "Magic System")
    entity = graph.create_entity(bare.id, "magic_system", "The Tide")
    assert entity.kind == "magic_system"
    assert graph.entity_types(bare.id) == {"magic_system"}


def test_a_malformed_type_name_is_rejected():
    for bad in ("", "  ", "9lives", "has spaces!", None, 7):
        with pytest.raises(TypeError_):
            normalize_type(bad)


# -- contradiction detection needs the application's judgement ------------

def test_without_declared_functional_predicates_nothing_is_flagged(graph):
    """The core cannot tell a contradiction from a character legitimately being
    both brave and reckless — only the application knows which predicates are
    single-valued, so with none declared it reports nothing rather than guessing."""
    from creativeos_engine.graph import ValidWindow

    bare = graph.create_space("Untyped", domain="general")
    graph.declare_entity_type(bare.id, "character")
    kell = graph.create_entity(bare.id, "character", "Kell Varo")
    graph.assert_attribute(kell.id, "status", "alive", valid=ValidWindow(0, 400))
    graph.assert_attribute(kell.id, "status", "dead", valid=ValidWindow(300, 600))

    assert graph.contradictions(bare.id) == []


# -- Identity Engine: identity survives renames ---------------------------

def test_identity_survives_a_rename(graph, space, cast):
    """*"Identity survives renames."* The id is the identity; the name is a label."""
    kell = cast["kell"]
    graph.assert_attribute(kell.id, "rank", "second mate")
    graph.assert_relationship(kell.id, "born_in", cast["harbour"].id)

    renamed = graph.rename_entity(kell.id, "Kell Varo-Ianto")

    assert renamed.id == kell.id
    assert renamed.name == "Kell Varo-Ianto"
    assert graph.state_of(kell.id)["rank"] == "second mate"
    assert len(graph.neighbors(kell.id)) == 1
