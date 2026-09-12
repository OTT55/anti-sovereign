"""Phase 4 — typed relationships, read out of the prose.

The app requires every relationship to be entered by hand. The draft states
most of them.
"""

from storyatlas_engine import read


def _relations(text):
    return {(r.subject, r.relation, r.target) for r in read(text).relations}


# -- stated relationships ---------------------------------------------------

def test_a_predicate_relationship_is_extracted():
    found = _relations("Mara Sadel married Tobin Reyes in the year 1140.")
    assert ("Mara Sadel", "spouse", "Tobin Reyes") in found


def test_a_hierarchy_relationship_is_extracted():
    found = _relations("Tobin Reyes served under Admiral Locke for a decade.")
    assert ("Tobin Reyes", "served_under", "Admiral Locke") in found


def test_a_possessive_kinship_is_extracted():
    found = _relations("Aldric Vane's daughter Mara Sadel took the throne.")
    assert ("Mara Sadel", "daughter_of", "Aldric Vane") in found


def test_an_appositive_kinship_is_extracted():
    found = _relations("Mara Sadel, daughter of Aldric Vane, took the throne.")
    assert ("Mara Sadel", "daughter_of", "Aldric Vane") in found


def test_betrayal_is_directional():
    found = _relations("Tobin Reyes betrayed Aldric Vane at Dawnhold.")
    assert ("Tobin Reyes", "betrayed", "Aldric Vane") in found
    assert ("Aldric Vane", "betrayed", "Tobin Reyes") not in found


# -- inverses ---------------------------------------------------------------

def test_a_kinship_inverse_is_derived():
    """A graph storing only "Mara is Aldric's daughter" cannot answer "who are
    Aldric's children" — the same fact asked the other way round."""
    found = _relations("Aldric Vane's daughter Mara Sadel took the throne.")
    assert ("Aldric Vane", "parent_of", "Mara Sadel") in found


def test_a_symmetric_relationship_gets_its_mirror():
    found = _relations("Mara Sadel married Tobin Reyes.")
    assert ("Tobin Reyes", "spouse", "Mara Sadel") in found


def test_an_inferred_relation_is_labelled_as_such():
    r = read("Aldric Vane's daughter Mara Sadel took the throne.")
    inferred = [rel for rel in r.relations if rel.inferred]
    assert inferred
    assert all(rel.confidence < 1.0 for rel in inferred)


def test_a_gendered_inverse_is_not_invented():
    """"Aldric is Mara's parent" is safe; choosing father over mother is not."""
    found = _relations("Aldric Vane's daughter Mara Sadel took the throne.")
    assert not any(rel == "father_of" for _s, rel, _t in found)


def test_an_asymmetric_relationship_is_not_mirrored():
    found = _relations("Tobin Reyes served under Admiral Locke.")
    assert ("Admiral Locke", "served_under", "Tobin Reyes") not in found


# -- hygiene ----------------------------------------------------------------

def test_nothing_relates_to_itself():
    r = read("Aldric Vane betrayed Aldric Vane.")
    assert all(rel.subject != rel.target for rel in r.relations)


def test_relations_are_not_duplicated():
    r = read(
        "Mara Sadel married Tobin Reyes. "
        "Mara Sadel married Tobin Reyes."
    )
    keys = [rel.key() for rel in r.relations]
    assert len(keys) == len(set(keys))


def test_every_relation_cites_its_sentence():
    r = read("Mara Sadel married Tobin Reyes in the year 1140.")
    assert r.relations
    for rel in r.relations:
        assert rel.evidence
        assert rel.sentence_index is not None


def test_relations_can_be_looked_up_per_character():
    r = read("Mara Sadel married Tobin Reyes. Tobin Reyes served under Admiral Locke.")
    assert {rel.relation for rel in r.relations_for("Tobin Reyes")} \
        >= {"served_under", "spouse"}


def test_stated_and_inferred_can_be_separated():
    r = read("Mara Sadel married Tobin Reyes.")
    assert all(not rel.inferred for rel in r.stated_relations())


def test_extraction_is_deterministic():
    text = "Aldric Vane's daughter Mara Sadel married Tobin Reyes."
    assert _relations(text) == _relations(text)
