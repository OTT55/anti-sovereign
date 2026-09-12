"""Phase 8 — reconciling people with places and time.

The bug these tests exist for, in the writer's words: *"there are people
supposed to be dead in the future, but they are alive, which makes no sense."*
"""

import pytest

from storyatlas_engine import analyse, read
from storyatlas_engine import presence


# The draft that exposed the problem. Mara dies in 1135 and is still talking in
# 1160, and nothing before Phase 8 noticed, because she appears in a *scene*
# rather than as the subject of a dated event.
HAUNTED = """CHAPTER ONE

Aldric Vane was born in the year 1102. Dawnhold was founded in the year 1090.

***

He was crowned at the age of thirty. Three years later, the war began.
Mara Sadel died that same year.

***

CHAPTER TWO

In the year 1160, the council gathered at Dawnhold. Mara Sadel spoke against
the treaty. Aldric Vane watched her.
"""


@pytest.fixture
def haunted():
    return read(HAUNTED)


# -- the regression that made everything else possible ----------------------

def test_a_pronoun_never_resolves_to_a_castle(haunted):
    """"Dawnhold was founded… He was crowned…" must not crown the castle.

    Worth its own test because the visible symptom is nowhere near the cause.
    Attaching "he" to a place leaves the coronation with no birth to count from,
    so it stays undated, so the next sentence's "three years later" anchors to
    the founding instead — and a death lands decades early.
    """
    accession = haunted.timeline.by_kind("accession")
    assert accession
    assert accession[0].event.subject == "Aldric Vane"
    assert accession[0].year == 1132        # 1102 + 30, not 1090 + anything


def test_the_date_chain_survives_an_intervening_place(haunted):
    """Everything downstream of that pronoun resolves correctly."""
    _born, died = presence.character_lifespans(haunted)["Mara Sadel"]
    assert died == 1135                     # 1132 + 3, "that same year"


# -- dating the scenes ------------------------------------------------------

def test_every_scene_gets_a_position_in_time(haunted):
    dates = presence.date_scenes(haunted)
    assert len(dates) == len(haunted.scenes)
    assert all(d.year is not None for d in dates)


def test_a_scene_keeps_its_span_not_just_a_point(haunted):
    """A scene covering 1090 and 1102 is thirteen years wide, and saying it is
    "in 1090" is what makes a birth scene look like a continuity error."""
    first = presence.date_scenes(haunted)[0]
    assert (first.low, first.high) == (1090, 1102)
    assert first.spans_years


def test_a_scene_with_no_time_signal_carries_the_previous_one():
    reading = read("Aldric Vane was born in the year 1102.\n\n***\n\nHe rode north.")
    dates = presence.date_scenes(reading)
    assert dates[-1].year == 1102
    assert dates[-1].source == "carried"
    assert not dates[-1].is_firm        # an assumption, and marked as one


def test_a_carried_date_cannot_produce_an_error():
    """A conclusion is only as strong as its weakest date."""
    reading = read(
        "Mara Sadel died in the year 1100.\n\n***\n\nMara Sadel spoke again.")
    found = presence.reconcile(reading)
    assert all(v.severity == "warning" for v in found if v.rule == "posthumous")


# -- existence intervals ----------------------------------------------------

def test_a_place_that_fell_is_not_a_character_who_died():
    """"Dawnhold fell in 1140" and "Aldric fell in 1140" produce the same event
    kind. Untyped, a castle acquires a date of death and the engine starts
    comparing people's births against it."""
    reading = read(
        "Dawnhold was founded in the year 1090. Dawnhold fell in the year 1140. "
        "Aldric Vane was born in the year 1150.")
    assert "Dawnhold" not in presence.character_lifespans(reading)
    dawnhold = presence.existences(reading)["Dawnhold"]
    assert (dawnhold.begins, dawnhold.ends) == (1090, 1140)


def test_an_unbounded_existence_decides_nothing():
    existence = presence.Existence("Nobody", "character")
    assert existence.contains(1200) is None
    assert not existence.is_bounded


def test_intervals_that_touch_do_not_conflict():
    existence = presence.Existence("Aldric", "character", begins=1100, ends=1150)
    assert existence.contains(1150) is True
    assert existence.contains(1151) is False


# -- the headline rules -----------------------------------------------------

def test_a_dead_character_in_a_later_scene_is_an_error(haunted):
    found = presence.reconcile(haunted)
    posthumous = [v for v in found if v.rule == "posthumous"]
    assert posthumous
    assert posthumous[0].subject == "Mara Sadel"
    assert "1135" in posthumous[0].text and "1160" in posthumous[0].text
    assert posthumous[0].severity == "error"


def test_the_birth_scene_is_not_accused_of_a_prenatal_appearance(haunted):
    """Scene 1 narrates Aldric's birth and is dated from 1090. Checking presence
    against a single point would flag him as appearing twelve years early."""
    found = presence.reconcile(haunted)
    assert not [v for v in found if v.rule == "prenatal"]


def test_a_character_named_as_the_object_is_still_present():
    """"The council summoned Aldric" makes Aldric the patient. He does nothing,
    and he is unambiguously there."""
    reading = read(
        "Aldric Vane died in the year 1100. "
        "In the year 1150, Mara Sadel betrayed Aldric Vane.")
    found = presence.reconcile(reading)
    assert [v for v in found if v.rule == "posthumous" and v.subject == "Aldric Vane"]


def test_standing_in_a_place_that_has_already_fallen():
    reading = read(
        "Dawnhold was founded in the year 1000. Dawnhold fell in the year 1100. "
        "In the year 1200, Aldric Vane was crowned at Dawnhold.")
    found = presence.reconcile(reading)
    assert [v for v in found if v.rule == "place-gone"]


def test_standing_in_a_place_that_does_not_exist_yet():
    reading = read(
        "Emberfall was founded in the year 1300. "
        "In the year 1100, Aldric Vane was crowned at Emberfall.")
    found = presence.reconcile(reading)
    assert [v for v in found if v.rule == "place-not-yet"]


def test_two_characters_whose_lives_never_overlapped_cannot_share_a_scene():
    reading = read(
        "Aldric Vane was born in the year 1100. Aldric Vane died in the year 1150. "
        "Kesh Oru was born in the year 1400.\n\n***\n\n"
        "Aldric Vane met Kesh Oru.")
    found = presence.reconcile(reading)
    assert [v for v in found if v.rule == "impossible-meeting"]


def test_a_finding_points_at_the_sentence_that_names_the_character(haunted):
    """A finding a writer cannot navigate to is one they will not act on — and
    every offered fix edits a sentence, so a finding with no sentence has no fix
    that does anything."""
    posthumous = next(v for v in presence.reconcile(haunted)
                      if v.rule == "posthumous")
    assert posthumous.sentence_index is not None
    sentence = haunted.sentences[posthumous.sentence_index]
    assert "Mara Sadel" in sentence.text
    assert "1160" not in sentence.text or "spoke" in sentence.text


def test_a_writer_can_mark_an_anomaly_deliberate_in_the_text():
    """A flashback, a vision and a ghost are all real techniques. A checker that
    cannot be told "yes, I meant that" is one a writer switches off."""
    marked = HAUNTED.replace(
        "Mara Sadel spoke against\nthe treaty.",
        "Mara Sadel spoke against\nthe treaty [deliberate: she is a ghost].")
    assert not [v for v in presence.reconcile(read(marked))
                if v.rule == "posthumous"]


def test_the_marker_exempts_only_the_sentence_it_is_on():
    reading = read(
        "Mara Sadel died in the year 1100.\n\n***\n\n"
        "In the year 1200, Mara Sadel spoke [deliberate: a vision] at Dawnhold. "
        "In the year 1200, Mara Sadel betrayed Aldric Vane.")
    found = [v for v in presence.reconcile(reading) if v.rule == "posthumous"]
    assert found
    assert all("betrayed" in v.evidence for v in found)


def test_nothing_is_reported_when_the_dates_are_missing():
    """A rule that cannot be evaluated stays silent. A checker that cries wolf
    gets switched off, and then it catches nothing at all."""
    reading = read("Aldric Vane rode north. Mara Sadel waited at Dawnhold.")
    assert presence.reconcile(reading) == []


def test_a_contradiction_is_reported_once():
    reading = read(
        "Mara Sadel died in the year 1100.\n\n***\n\n"
        "In the year 1200, Mara Sadel betrayed Aldric Vane at Dawnhold.")
    found = presence.reconcile(reading)
    keys = [(v.rule, v.subject, v.sentence_index, v.text) for v in found]
    assert len(keys) == len(set(keys))


# -- the derived views ------------------------------------------------------

def test_an_itinerary_puts_one_character_in_order():
    reading = read(
        "In the year 1100, Aldric Vane was crowned at Dawnhold. "
        "In the year 1120, Aldric Vane died at Emberfall.")
    steps = presence.itinerary(reading, "Aldric Vane")
    assert [y for y, _p in steps] == sorted(y for y, _p in steps)
    assert ("Dawnhold" in [p for _y, p in steps])


def test_occupancy_is_the_mirror_of_an_itinerary():
    reading = read("In the year 1100, Aldric Vane was crowned at Dawnhold.")
    where = presence.occupancy(reading)
    assert "Aldric Vane" in where.get("Dawnhold", {}).get(1100, [])


def test_reconciliation_reaches_the_report():
    """The report merges Phase 5's rules with Phase 8's. A writer should not
    have to learn which module found their problem."""
    report = analyse(HAUNTED)
    assert [v for v in report.errors if v.rule == "posthumous"]


def test_analysis_stays_deterministic():
    assert analyse(HAUNTED).render() == analyse(HAUNTED).render()
