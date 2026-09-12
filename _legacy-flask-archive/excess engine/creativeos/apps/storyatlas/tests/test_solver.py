"""Solving for dates the draft never states.

The point of the engine: a writer states a few dates and relates everything else
to them, and the rest is arithmetic.
"""

from storyatlas_engine import read


def test_one_stated_date_resolves_a_whole_chain():
    """Only 1102 is written down. Everything else is computed."""
    r = read(
        "Aldric Vane was born in the year 1102. "
        "He was crowned at the age of thirty. "
        "Three years later, the Meridian War began."
    )
    years = {p.event.kind: p.year for p in r.timeline.placements}
    assert years["birth"] == 1102
    assert years["accession"] == 1132       # 1102 + 30
    assert years["battle"] == 1135          # 1132 + 3


def test_that_same_year_takes_the_anchor_date():
    r = read(
        "The siege ended in the year 1140. "
        "Mara Sadel died that same year."
    )
    death = r.timeline.by_kind("death")[0]
    assert death.year == 1140


def test_a_backward_offset_goes_backwards():
    r = read(
        "The treaty was signed in the year 1150. "
        "Two years earlier, Tobin Reyes was crowned."
    )
    accession = r.timeline.by_kind("accession")[0]
    assert accession.year == 1148


def test_computed_dates_are_marked_as_computed():
    r = read(
        "Aldric Vane was born in the year 1102. "
        "Three years later, Aldric Vane was crowned."
    )
    by_kind = {p.event.kind: p for p in r.timeline.placements}
    assert by_kind["birth"].source == "stated"
    assert by_kind["accession"].source == "computed"


def test_an_undated_event_stays_undated_rather_than_being_guessed():
    r = read("Aldric Vane crossed the river and met Mara Sadel.")
    assert all(not p.is_dated for p in r.timeline.placements)
    assert r.timeline.undated


def test_a_clause_that_contradicts_itself_is_flagged():
    """States a year AND a relation that do not agree."""
    r = read(
        "Tobin Reyes was crowned in the year 1160. "
        "Three years later, Tobin Reyes died in the year 1150."
    )
    assert r.timeline.conflicts
    assert any("1163" in c["problem"] for c in r.timeline.conflicts)


def test_a_consistent_draft_reports_no_conflicts():
    r = read(
        "Aldric Vane was born in the year 1102. "
        "He was crowned at the age of thirty. "
        "Three years later, the Meridian War began."
    )
    assert r.timeline.conflicts == []


def test_solving_is_deterministic():
    draft = (
        "Aldric Vane was born in the year 1102. "
        "He was crowned at the age of thirty. "
        "Three years later, the Meridian War began."
    )
    first = [(p.event.kind, p.year) for p in read(draft).timeline.in_order()]
    second = [(p.event.kind, p.year) for p in read(draft).timeline.in_order()]
    assert first == second
