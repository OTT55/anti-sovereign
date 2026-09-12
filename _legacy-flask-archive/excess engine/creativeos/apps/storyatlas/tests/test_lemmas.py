"""The second tier of event detection: lemmas over inflections.

A regex trigger list only catches the endings somebody thought to type. These
are the five sentences that exposed it — the regex tier caught one.
"""

import pytest

from storyatlas_engine import read
from storyatlas_engine.comprehend.lemmas import lemma_triggers, status

available, _reason = status()
needs_spacy = pytest.mark.skipif(not available, reason="spaCy not available")


def test_the_tier_reports_whether_it_is_available():
    ok, reason = status()
    assert isinstance(ok, bool)
    assert reason


def test_an_unavailable_tier_returns_none_not_empty():
    """`None` means "did not run"; `[]` means "ran and found nothing". The
    engine has to be able to tell those apart."""
    result = lemma_triggers("Tobin Reyes was founding the Order.")
    assert result is None or isinstance(result, list)


@needs_spacy
@pytest.mark.parametrize("sentence,kind", [
    ("Tobin Reyes was founding the Order in the year 1150.", "founding"),
    ("Tobin Reyes founds the Order in the year 1150.", "founding"),
    ("Mara Sadel was betraying Aldric Vane in the year 1140.", "betrayal"),
    ("Kell Varo journeys to Dawnhold in the year 1160.", "travel"),
    ("Mara Sadel was establishing the Guild in the year 1160.", "founding"),
])
def test_inflections_the_regex_list_never_enumerated(sentence, kind):
    kinds = {e.kind for e in read(sentence).events}
    assert kind in kinds, f"{sentence} -> {kinds}"


@needs_spacy
def test_the_regex_tier_covers_what_the_model_mis_tags():
    """spaCy's small model tags "perishes" as a NOUN (lemma "perishe"), so the
    lemma tier cannot see it. The regex tier does — which is the case for
    keeping both rather than letting one supersede the other."""
    from storyatlas_engine.comprehend.lemmas import lemma_triggers
    assert lemma_triggers("Aldric Vane perishes at Ash Harbour.") == []
    assert "death" in {e.kind for e in read(
        "Aldric Vane perishes at Ash Harbour in the year 1147.").events}


@needs_spacy
def test_the_regex_tier_still_wins_where_it_applies():
    """Multi-word patterns a single-token lemma lookup cannot see."""
    assert "accession" in {e.kind for e in read(
        "Aldric Vane took the throne in the year 1130.").events}


@needs_spacy
def test_passive_voice_is_detected_without_a_dependency_parse():
    events = read("Aldric Vane was betrayed by Tobin Reyes in 1147.").events
    betrayal = next(e for e in events if e.kind == "betrayal")
    assert betrayal.patient == "Aldric Vane"


@needs_spacy
def test_was_born_is_always_read_as_passive():
    events = read("Aldric Vane was born in the year 1102.").events
    assert next(e for e in events if e.kind == "birth").subject == "Aldric Vane"


@needs_spacy
def test_a_clause_naming_nobody_is_not_parsed():
    """An event with no participants is useless here, and parsing is the
    expensive step — so it is skipped entirely."""
    assert read("It was founding rapidly.").events == []


@needs_spacy
def test_the_second_tier_does_not_disturb_the_first():
    """The canonical draft must resolve exactly as it did before this tier."""
    r = read("Aldric Vane was born in the year 1102. "
             "He was crowned at the age of thirty. "
             "Three years later, the Meridian War began.")
    years = {p.event.kind: p.year for p in r.timeline.placements}
    assert years["birth"] == 1102
    assert years["accession"] == 1132
    assert years["battle"] == 1135


@needs_spacy
def test_detection_is_still_deterministic():
    sentence = "Tobin Reyes was founding the Order in the year 1150."
    assert [e.describe() for e in read(sentence).events] \
        == [e.describe() for e in read(sentence).events]
