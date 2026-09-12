"""Understanding what happened and to whom — the gap this engine exists to close.

The existing Story Atlas stores an event as the raw sentence plus a
keyword-guessed category, with no link to the people in it. So "who died?"
is unanswerable and nothing can be grouped. These tests are that capability.
"""

from storyatlas_engine import read


# -- who it happened to ----------------------------------------------------

def test_a_death_knows_whose_death_it_is():
    r = read("Aldric Vane died in the year 1147.")
    death = r.timeline.by_kind("death")[0]
    assert death.event.subject == "Aldric Vane"


def test_a_passive_killing_puts_the_victim_and_the_killer_the_right_way_round():
    """"Aldric was killed by Tobin" names the same two people in the same order
    as "Aldric killed Tobin" and means the opposite."""
    r = read("Aldric Vane was killed by Tobin Reyes in the year 1147.")
    event = r.timeline.by_kind("death")[0].event
    assert event.patient == "Aldric Vane"     # the victim
    assert event.agent == "Tobin Reyes"       # the killer
    assert event.subject == "Aldric Vane"


def test_an_active_killing_is_read_correctly():
    r = read("Tobin Reyes killed Aldric Vane in the year 1147.")
    event = r.timeline.by_kind("death")[0].event
    assert event.agent == "Tobin Reyes"
    assert event.patient == "Aldric Vane"


def test_a_place_is_not_mistaken_for_a_participant():
    r = read("Mara Sadel died at Dawnhold in the year 1140.")
    event = r.timeline.by_kind("death")[0].event
    assert event.subject == "Mara Sadel"
    assert event.place == "Dawnhold"


def test_two_events_in_one_sentence_are_separated():
    """Without clause splitting the second event silently inherits the first's
    subject and date."""
    r = read(
        "Aldric Vane died in the year 1147 and Mara Sadel was crowned that same year."
    )
    kinds = {p.event.kind for p in r.timeline.placements}
    assert "death" in kinds and "accession" in kinds


# -- grouping --------------------------------------------------------------

DRAFT = (
    "Aldric Vane was born in the year 1102. "
    "Mara Sadel was born in the year 1110. "
    "Aldric Vane died in the year 1147. "
    "Mara Sadel died in the year 1150. "
    "Tobin Reyes founded the Order of the Broken Crown in the year 1152."
)


def test_who_died_and_when():
    """The question the current app cannot answer."""
    deaths = dict(read(DRAFT).deaths())
    assert deaths["Aldric Vane"] == 1147
    assert deaths["Mara Sadel"] == 1150


def test_events_group_by_kind():
    grouped = read(DRAFT).by_kind()
    assert len(grouped["death"]) == 2
    assert len(grouped["birth"]) == 2


def test_events_group_by_person():
    by_person = read(DRAFT).by_person()
    kinds = [p.event.kind for p in by_person["Aldric Vane"]]
    assert "birth" in kinds and "death" in kinds


def test_events_group_into_periods():
    periods = read(DRAFT).by_period(span=50)
    assert 1100 in periods
    assert 1150 in periods


def test_lifespans_are_derived():
    spans = read(DRAFT).lifespans()
    assert spans["Aldric Vane"] == (1102, 1147)
    assert spans["Mara Sadel"] == (1110, 1150)


def test_the_timeline_is_chronological():
    years = [p.year for p in read(DRAFT).timeline.in_order() if p.is_dated]
    assert years == sorted(years)


# -- asking rather than guessing -------------------------------------------

def test_a_character_acting_after_their_own_death_is_questioned():
    r = read(
        "Sera Locke was born in the year 1100. "
        "Sera Locke died in the year 1140. "
        "In 1155, Sera Locke signed the Dawnhold Accord."
    )
    lifespan = [q for q in r.questions if q.kind == "lifespan"]
    assert lifespan
    assert "1140" in lifespan[0].text and "1155" in lifespan[0].text


def test_a_carried_over_pronoun_is_confirmed_not_assumed():
    r = read(
        "Aldric Vane was born in the year 1102. "
        "He was crowned at the age of thirty."
    )
    pronoun = [q for q in r.questions if q.kind == "pronoun"]
    assert pronoun
    assert pronoun[0].about == "Aldric Vane"


def test_an_undated_event_produces_a_when_question():
    r = read("Aldric Vane met Mara Sadel in the great hall.")
    assert any(q.kind == "when" for q in r.questions)


def test_every_question_cites_its_evidence():
    """A question without the sentence that prompted it is unanswerable."""
    r = read(
        "Sera Locke was born in the year 1100. "
        "Sera Locke died in the year 1140. "
        "In 1155, Sera Locke signed the Dawnhold Accord."
    )
    assert r.questions
    for q in r.questions:
        assert q.evidence
        assert q.sentence_index is not None


def test_the_summary_reports_what_was_computed_versus_stated():
    r = read(
        "Aldric Vane was born in the year 1102. "
        "He was crowned at the age of thirty. "
        "Three years later, the Meridian War began."
    )
    summary = r.summary()
    assert summary["events"] == 3
    assert summary["dated_events"] == 3
    assert summary["computed_dates"] == 2
