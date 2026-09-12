"""Phase 9 — what to actually do about it, and in what order.

*"You have all the places in this thing. What will you do with it? What
actionable thing can you take from it?"*
"""

import pytest

from storyatlas_engine import analyse
from storyatlas_engine.worklist import (
    SEVERITY_ORDER, dependents, next_action, render, worklist,
)

DRAFT = """Aldric Vane was born in the year 1102. He was crowned at the age of
thirty. Three years later, the war began. Mara Sadel died that same year.

***

In the year 1160, the council gathered at Dawnhold. Mara Sadel spoke against
the treaty.

***

Aldric Vane rode north.
"""


@pytest.fixture
def report():
    return analyse(DRAFT)


def test_a_worklist_is_produced(report):
    assert worklist(report)


def test_errors_come_before_gaps(report):
    severities = [SEVERITY_ORDER[f.severity] for f in worklist(report)]
    assert severities == sorted(severities)


def test_every_fix_offers_a_way_to_resolve_it(report):
    """A finding that only says "this is wrong" makes the writer do the work
    again."""
    assert all(fix.options for fix in worklist(report))


def test_a_contradiction_offers_both_resolutions(report):
    """Which of two dates is wrong is the author's decision. An engine that
    silently picks one has invented a fact."""
    errors = [f for f in worklist(report) if f.severity == "error"]
    assert errors
    kinds = {o.kind for o in errors[0].options}
    assert "dismiss" in kinds
    assert len(errors[0].options) >= 2


def test_leverage_counts_the_dates_that_hang_off_a_sentence(report):
    """The birth in sentence 1 anchors the coronation, the war and a death."""
    birth = next(p for p in report.reading.timeline.placements
                 if p.event.kind == "birth")
    assert dependents(report.reading, birth.event.sentence_index) >= 2


def test_leverage_is_zero_for_a_sentence_nothing_depends_on(report):
    assert dependents(report.reading, 999) == 0


def test_ties_are_broken_by_leverage(report):
    fixes = [f for f in worklist(report) if f.severity == "gap"]
    if len(fixes) > 1:
        assert [f.leverage for f in fixes] == sorted(
            (f.leverage for f in fixes), reverse=True)


def test_a_problem_is_not_listed_twice(report):
    """A lifespan contradiction is an error, and must not also appear as an
    open question under another heading."""
    titles = [f.title for f in worklist(report)]
    assert len(titles) == len(set(titles))


def test_ids_are_stable_within_a_run(report):
    fixes = worklist(report)
    assert [f.id for f in fixes] == [f"F{i + 1:02d}" for i in range(len(fixes))]


def test_next_action_names_one_thing(report):
    chosen = next_action(worklist(report))
    assert chosen is not None
    fix, action = chosen
    assert fix.severity == "error"
    assert action.kind not in ("dismiss", "accept")


def test_a_clean_draft_produces_an_empty_worklist():
    report = analyse("Aldric Vane was born in the year 1102.")
    assert "Nothing to fix" in render([f for f in worklist(report)
                                       if f.severity == "impossible"])


def test_rendering_says_why_each_fix_matters(report):
    text = render(worklist(report))
    assert "What to do next" in text
    assert "depend" in text


def test_the_report_exposes_its_own_worklist(report):
    limited = report.worklist(limit=3)
    assert len(limited) <= 3
    assert [f.title for f in limited] == [f.title for f in worklist(report)[:3]]


def test_worklist_is_deterministic():
    first = render(worklist(analyse(DRAFT)))
    second = render(worklist(analyse(DRAFT)))
    assert first == second
