"""Did it actually happen?

The bug: a trigger verb was enough on its own, so "Aldric did NOT die in 1147"
recorded a death. For a continuity engine that is the worst class of error — a
missed event leaves a visible gap, but an event the text explicitly denies puts
a false fact in the timeline, and every date computed from it, lifespan bounded
by it, and contradiction checked against it inherits the mistake.
"""

import pytest

from storyatlas_engine import read
from storyatlas_engine.comprehend.factuality import (
    ASSERTED, FUTURE, HYPOTHETICAL, INTERROGATIVE, NEGATED, classify,
)


# -- classification --------------------------------------------------------

@pytest.mark.parametrize("clause,expected", [
    ("Aldric Vane died in the year 1147.", ASSERTED),
    ("Aldric Vane did not die in the year 1147.", NEGATED),
    ("Aldric Vane never returned to Dawnhold.", NEGATED),
    ("If Aldric Vane had died, the war would have ended.", HYPOTHETICAL),
    ("Aldric Vane would have died at Dawnhold.", HYPOTHETICAL),
    ("Aldric Vane will die in the year 1147.", FUTURE),
    ("Aldric Vane may have died at Dawnhold.", FUTURE),
    ("Aldric Vane plans to found the Order.", FUTURE),
])
def test_clauses_are_classified(clause, expected):
    assert classify(clause) == expected


def test_a_question_is_recognised_from_the_whole_sentence():
    """The question mark lives at the end of the sentence and is usually gone
    by the time a clause is split out."""
    assert classify("Aldric Vane die in 1147",
                    "Did Aldric Vane die in 1147?") == INTERROGATIVE


def test_a_question_about_a_negation_is_still_a_question():
    assert classify("did not die", "Did Aldric not die in 1147?") == INTERROGATIVE


# -- the timeline stays clean ----------------------------------------------

@pytest.mark.parametrize("text", [
    "Aldric Vane did not die in the year 1147.",
    "If Aldric Vane had died in 1147, the war would have ended.",
    "Aldric Vane will die in the year 1147.",
    "Did Aldric Vane die in the year 1147?",
])
def test_an_unasserted_event_never_reaches_the_timeline(text):
    reading = read(text)
    assert reading.timeline.placements == []
    assert reading.deaths() == []


def test_a_plain_statement_still_becomes_a_fact():
    """The fix must not buy safety by refusing to record anything."""
    reading = read("Aldric Vane died in the year 1147.")
    assert reading.deaths() == [("Aldric Vane", 1147)]


def test_an_unasserted_event_is_surfaced_not_dropped():
    """Silently discarding it would be its own kind of dishonesty."""
    reading = read("Aldric Vane did not die in the year 1147.")
    assert len(reading.non_factual) == 1
    assert any(q.kind == "not-asserted" for q in reading.questions)


def test_the_question_says_why_it_was_not_recorded():
    reading = read("If Aldric Vane had died in 1147, the war would have ended.")
    question = next(q for q in reading.questions if q.kind == "not-asserted")
    assert "hypothetical" in question.text


def test_a_denial_does_not_create_a_lifespan():
    """The compounding failure: a false death bounds a life, and every later
    check against that lifespan inherits the error."""
    reading = read("Aldric Vane was born in 1102. "
                   "Aldric Vane did not die in the year 1147.")
    born, died = reading.lifespans().get("Aldric Vane", (None, None))
    assert born == 1102
    assert died is None


def test_a_denial_does_not_poison_a_computed_date():
    """A false anchor would drag every date chained from it."""
    reading = read("Aldric Vane was born in the year 1102. "
                   "Aldric Vane did not die three years later.")
    years = [p.year for p in reading.timeline.placements]
    assert years == [1102]


def test_mixed_text_keeps_the_facts_and_drops_the_rest():
    reading = read(
        "Aldric Vane was born in the year 1102. "
        "He did not die at Ash Harbour. "
        "Aldric Vane died in the year 1147.")
    assert reading.deaths() == [("Aldric Vane", 1147)]
    assert reading.non_factual


# -- the "and" fix ---------------------------------------------------------

def test_two_names_joined_by_and_are_two_people():
    """Regression: "Aldric Vane and Mara Sadel" became a single entity of that
    name, which then matched nothing and lost both characters."""
    reading = read("Aldric Vane and Mara Sadel died in the year 1147.")
    assert "Aldric Vane" in reading.names
    assert "Mara Sadel" in reading.names
    assert "Aldric Vane and Mara Sadel" not in reading.names


def test_a_name_containing_a_connective_still_holds_together():
    reading = read("Tobin Reyes founded the Order of the Broken Crown in 1150. "
                   "The Order of the Broken Crown endured.")
    assert "Order of the Broken Crown" in reading.names
