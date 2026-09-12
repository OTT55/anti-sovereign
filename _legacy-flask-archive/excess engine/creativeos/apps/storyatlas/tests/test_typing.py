"""Phase 2 — deciding what kind of thing each name is.

Phase 1 treated every name alike, so an organisation could appear in a
per-person grouping. Typing is what makes grouping actually correct.
"""

from storyatlas_engine import read

DRAFT = (
    "Chancellor Aldric Vane was born in the year 1102 in the city of Dawnhold. "
    "He was crowned at the age of thirty. "
    "Three years later, the Meridian War began. "
    "Mara Sadel died that same year at Dawnhold. "
    "Aldric was killed by Tobin Reyes two years later. "
    "A decade later, Tobin Reyes founded the Order of the Broken Crown."
)


def test_people_are_identified():
    r = read(DRAFT)
    assert "Chancellor Aldric Vane" in r.people()
    assert "Mara Sadel" in r.people()


def test_an_actor_is_a_person_even_without_a_title():
    """Tobin only ever kills and founds — no title, no dialogue. Acting is
    itself the evidence: only people act."""
    assert "Tobin Reyes" in read(DRAFT).people()


def test_an_organization_is_not_a_person():
    r = read(DRAFT)
    assert "Order of the Broken Crown" in r.organizations()
    assert "Order of the Broken Crown" not in r.people()


def test_a_named_war_is_an_event():
    assert "Meridian War" in read(DRAFT).named_events()


def test_a_place_is_identified_from_how_it_is_used():
    assert "Dawnhold" in read(DRAFT).places()


def test_per_person_grouping_excludes_non_people():
    """The Phase 1 gap this phase exists to close."""
    grouped = read(DRAFT).by_person()
    assert "Order of the Broken Crown" not in grouped
    assert "Meridian War" not in grouped
    assert "Chancellor Aldric Vane" in grouped


def test_every_name_can_still_be_seen_when_asked_for():
    grouped = read(DRAFT).by_person(people_only=False)
    assert "Order of the Broken Crown" in grouped


def test_typing_works_on_invented_words():
    """No gazetteer — "Ravenmoor" is a place because of how the text uses it."""
    r = read(
        "Kestrel Vane fled to Ravenmoor in the year 1200. "
        "Kestrel Vane died at Ravenmoor in the year 1210."
    )
    assert "Ravenmoor" in r.places()
    assert "Kestrel Vane" in r.people()


def test_a_house_reads_as_an_organization():
    r = read(
        "The House of Aldermere ruled for a century. "
        "The House of Aldermere was founded in the year 1000."
    )
    assert "House of Aldermere" in r.organizations()


def test_an_ambiguous_name_is_asked_about_not_guessed():
    r = read("Blackmere endured. Blackmere remained.")
    unclear = [q for q in r.questions if q.kind == "type"]
    # Either it typed it confidently, or it asked — never a silent coin-flip.
    assert unclear or r.kind_of("Blackmere") != "other"


def test_cast_groups_everything_by_kind():
    cast = read(DRAFT).cast()
    assert "character" in cast
    assert "organization" in cast
    assert "location" in cast


def test_typing_is_deterministic():
    assert read(DRAFT).cast() == read(DRAFT).cast()
