"""Phase 5 — canon rules beyond a lifespan."""

from storyatlas_engine import analyse


def _rules(text):
    return {v.rule for v in analyse(text).violations}


def test_an_organisation_cannot_act_before_it_is_founded():
    text = (
        "Tobin Reyes founded the Broken Crown in the year 1150. "
        "The Broken Crown betrayed Aldric Vane in the year 1100."
    )
    assert "founding" in _rules(text)


def test_an_organisation_acting_after_founding_is_fine():
    text = (
        "Tobin Reyes founded the Broken Crown in the year 1100. "
        "The Broken Crown betrayed Aldric Vane in the year 1150."
    )
    assert "founding" not in _rules(text)


def test_a_character_cannot_be_in_two_places_in_one_year():
    text = (
        "Aldric Vane died at Ash Harbour in the year 1147. "
        "Aldric Vane was killed at Dawnhold in the year 1147."
    )
    assert "location" in _rules(text)


def test_a_character_cannot_act_before_being_born():
    text = (
        "Mara Sadel was born in the year 1150. "
        "Mara Sadel betrayed Aldric Vane in the year 1100."
    )
    assert "unborn" in _rules(text)


def test_a_relationship_between_non_overlapping_lives_is_flagged():
    text = (
        "Aldric Vane was born in the year 1000. "
        "Aldric Vane died in the year 1050. "
        "Mara Sadel was born in the year 1200. "
        "Aldric Vane married Mara Sadel."
    )
    assert "relationship" in _rules(text)


def test_two_people_taking_one_office_at_once_is_warned():
    text = (
        "Aldric Vane was crowned in the year 1140. "
        "Mara Sadel was crowned in the year 1140."
    )
    violations = analyse(text).violations
    assert any(v.rule == "title" for v in violations)
    assert all(v.severity == "warning" for v in violations if v.rule == "title")


def test_an_orderly_handover_is_not_flagged():
    """The first holder had died — that is a succession, not a conflict."""
    text = (
        "Aldric Vane was crowned in the year 1100. "
        "Aldric Vane died in the year 1140. "
        "Mara Sadel was crowned in the year 1140."
    )
    assert "title" not in _rules(text)


def test_a_clean_draft_reports_nothing():
    text = (
        "Aldric Vane was born in the year 1100. "
        "Aldric Vane was crowned in the year 1130. "
        "Aldric Vane died in the year 1150."
    )
    assert analyse(text).violations == []


def test_a_rule_that_cannot_be_evaluated_stays_silent():
    """Undated events cannot violate anything. A checker that cries wolf gets
    switched off, and then it catches nothing at all."""
    text = "Mara Sadel betrayed Aldric Vane. Aldric Vane died."
    assert analyse(text).violations == []


def test_every_violation_cites_its_evidence():
    text = (
        "Mara Sadel was born in the year 1150. "
        "Mara Sadel betrayed Aldric Vane in the year 1100."
    )
    violations = analyse(text).violations
    assert violations
    for v in violations:
        assert v.text
        assert v.evidence


def test_errors_are_ordered_before_warnings():
    text = (
        "Mara Sadel was born in the year 1150. "
        "Mara Sadel betrayed Aldric Vane in the year 1100. "
        "Aldric Vane was crowned in the year 1140. "
        "Kell Varo was crowned in the year 1140."
    )
    severities = [v.severity for v in analyse(text).violations]
    assert severities == sorted(severities, key=lambda s: s != "error")


def test_canon_checking_is_deterministic():
    text = (
        "Mara Sadel was born in the year 1150. "
        "Mara Sadel betrayed Aldric Vane in the year 1100."
    )
    assert [v.describe() for v in analyse(text).violations] \
        == [v.describe() for v in analyse(text).violations]
