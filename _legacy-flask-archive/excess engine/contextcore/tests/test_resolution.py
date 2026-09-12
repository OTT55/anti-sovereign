"""Phase 3 — entity resolution and the maintained ontology.

The gap the constitution names directly: "resolve duplicate entities" and
"maintain canonical definitions".
"""

from contextcore_engine.resolution import (
    Ontology, name_similarity, normalize, resolve, types_compatible,
)


# -- normalisation ----------------------------------------------------------

def test_legal_forms_are_not_part_of_identity():
    assert normalize("Acme Corp") == normalize("Acme Corporation")
    assert normalize("Acme Inc.") == normalize("Acme")


def test_case_and_punctuation_are_stripped():
    assert normalize("ACME, Corp.") == normalize("acme corp")


# -- similarity -------------------------------------------------------------

def test_the_canonical_case_resolves():
    """"Acme Corp" and "Acme Corporation" were two entities that never met."""
    assert name_similarity("Acme Corp", "Acme Corporation") == 1.0


def test_a_typo_still_matches():
    assert name_similarity("Aldric Vane", "Aldrec Vane") > 0.8


def test_reordered_names_match():
    assert name_similarity("Vane, Aldric", "Aldric Vane") > 0.85


def test_unrelated_names_do_not_match():
    assert name_similarity("Acme Corporation", "Zenith Holdings") < 0.4


# -- type compatibility -----------------------------------------------------

def test_a_person_and_an_organization_never_merge():
    """The worst class of wrong merge, prevented by one cheap rule."""
    assert not types_compatible("person", "organization")


def test_the_same_type_is_always_compatible():
    assert types_compatible("organization", "organization")


# -- resolution -------------------------------------------------------------

def test_variants_of_one_name_become_one_entity():
    clusters = resolve([
        {"name": "Acme Corp", "type": "organization"},
        {"name": "Acme Corporation", "type": "organization"},
        {"name": "Acme", "type": "organization"},
    ])
    assert len(clusters) == 1
    assert clusters[0].canonical == "Acme Corporation"   # the fullest form


def test_distinct_entities_stay_distinct():
    clusters = resolve([
        {"name": "Acme Corporation", "type": "organization"},
        {"name": "Zenith Holdings", "type": "organization"},
    ])
    assert len(clusters) == 2


def test_a_shared_name_across_types_does_not_merge():
    clusters = resolve([
        {"name": "Meridian", "type": "organization"},
        {"name": "Meridian", "type": "place"},
    ])
    assert len(clusters) == 2


def test_a_cluster_keeps_every_alias_it_absorbed():
    clusters = resolve([
        {"name": "Acme Corporation", "type": "organization"},
        {"name": "Acme Corp", "type": "organization"},
    ])
    assert "Acme Corp" in clusters[0].aliases


def test_nameless_entities_are_dropped():
    assert resolve([{"name": "  ", "type": "organization"}]) == []


def test_resolution_is_deterministic():
    entities = [{"name": "Acme Corp", "type": "organization"},
                {"name": "Acme Corporation", "type": "organization"}]
    assert [c.describe() for c in resolve(entities)] \
        == [c.describe() for c in resolve(entities)]


# -- the ontology -----------------------------------------------------------

def test_a_declared_alias_resolves_to_its_canonical():
    onto = Ontology()
    onto.declare("Acme Corporation", "organization", aliases=["Acme", "ACME Inc"])
    assert onto.canonical_for("acme inc") == "Acme Corporation"


def test_an_unseen_but_similar_name_still_resolves():
    onto = Ontology()
    onto.declare("Acme Corporation", "organization")
    assert onto.canonical_for("Acme Corp") == "Acme Corporation"


def test_an_unknown_name_resolves_to_nothing():
    onto = Ontology()
    onto.declare("Acme Corporation", "organization")
    assert onto.canonical_for("Zenith Holdings") is None


def test_the_ontology_learns_from_a_resolution_pass():
    """Maintained, not re-decided: a name resolved once stays resolved."""
    onto = Ontology().learn(resolve([
        {"name": "Acme Corp", "type": "organization"},
        {"name": "Acme Corporation", "type": "organization"},
    ]))
    assert onto.canonical_for("Acme") == "Acme Corporation"
    assert onto.type_of("Acme Corporation") == "organization"


def test_the_ontology_reports_what_it_holds():
    onto = Ontology()
    onto.declare("Acme Corporation", "organization", aliases=["Acme"])
    onto.declare("Aldric Vane", "person")
    summary = onto.summary()
    assert summary["entities"] == 2
    assert "organization" in summary["types"]


def test_resolving_the_same_name_twice_is_stable():
    onto = Ontology()
    onto.declare("Acme Corporation", "organization")
    assert onto.canonical_for("Acme Corp") == onto.canonical_for("Acme Corp")
