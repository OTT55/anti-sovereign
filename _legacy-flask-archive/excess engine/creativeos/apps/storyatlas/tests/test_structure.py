"""Phases 6 and 7 — narrative structure and the coordinating report.

What is computable about a draft's shape, and — just as important — what this
deliberately does not claim to judge.
"""

from storyatlas_engine import analyse

DRAFT = """Aldric Vane waited at Ash Harbour in the year 1100.

Mara Sadel arrived. Mara Sadel spoke with Aldric Vane.

Kell Varo watched from the doorway.

Mara Sadel travelled to Dawnhold.

Mara Sadel was crowned in the year 1130.

Mara Sadel died in the year 1150.
"""


# -- threads ---------------------------------------------------------------

def test_each_character_gets_a_thread():
    names = {t.name for t in analyse(DRAFT).threads}
    assert "Mara Sadel" in names
    assert "Aldric Vane" in names


def test_a_thread_records_where_a_character_appears():
    thread = next(t for t in analyse(DRAFT).threads if t.name == "Mara Sadel")
    assert len(thread.scenes) >= 3
    assert thread.first_scene < thread.last_scene


def test_a_thread_shape_is_descriptive_not_evaluative():
    """"front-loaded" is a fact about the text; "badly paced" would be a
    judgement this cannot make."""
    for thread in analyse(DRAFT).threads:
        assert thread.shape in {
            "absent", "single-appearance", "continuous", "intermittent", "clustered",
        }


def test_a_character_in_one_scene_is_flagged_as_a_loose_end():
    kinds = {(o.kind, o.subject) for o in analyse(DRAFT).observations}
    assert ("loose-end", "Kell Varo") in kinds


# -- pacing ----------------------------------------------------------------

def test_pacing_reports_event_density_by_stretch():
    pacing = analyse(DRAFT).pacing
    assert pacing
    for bucket in pacing:
        assert "density" in bucket
        assert bucket["scenes"][0] <= bucket["scenes"][1]


def test_pacing_is_empty_for_an_empty_draft():
    assert analyse("").pacing == []


# -- the report ------------------------------------------------------------

def test_a_report_summarises_the_whole_draft():
    summary = analyse(DRAFT).summary()
    assert summary["scenes"] > 1
    assert summary["characters"] >= 2
    assert summary["events"] >= 3


def test_a_report_renders_readably():
    rendered = analyse(DRAFT).render()
    assert "# Draft report" in rendered
    assert "Characters" in rendered


def test_errors_and_warnings_are_separated():
    report = analyse(
        "Mara Sadel was born in the year 1150. "
        "Mara Sadel betrayed Aldric Vane in the year 1100."
    )
    assert report.errors
    assert all(v.severity == "error" for v in report.errors)
    assert all(v.severity == "warning" for v in report.warnings)


def test_continuity_errors_lead_the_report():
    """A break makes the draft wrong; a missing date makes it incomplete.

    The third sentence is load-bearing. Since Phase 8, a character acting
    outside their lifespan is reported as an error and no longer *also* as a
    question, so a draft whose only problem is that contradiction now has an
    empty "Needs confirmation" section. An undated event supplies a real
    question, which is what this test is actually about.
    """
    rendered = analyse(
        "Mara Sadel was born in the year 1150. "
        "Mara Sadel betrayed Aldric Vane in the year 1100. "
        "Aldric Vane travelled to Emberfall."
    ).render()
    assert rendered.index("Continuity errors") < rendered.index("Needs confirmation")


def test_a_contradiction_is_not_reported_twice():
    """The same problem under two headings teaches a writer to distrust both."""
    report = analyse(
        "Mara Sadel was born in the year 1150. "
        "Mara Sadel betrayed Aldric Vane in the year 1100."
    )
    assert report.errors
    assert not [q for q in report.reading.questions
                if q.kind == "lifespan" and q.text in report.render()]


def test_a_report_carries_the_questions_forward():
    report = analyse(
        "Aldric Vane was born in the year 1102. "
        "He was crowned at the age of thirty."
    )
    assert report.reading.questions
    assert "Needs confirmation" in report.render()


def test_an_empty_draft_does_not_crash():
    report = analyse("")
    assert report.summary()["scenes"] == 0
    assert report.render()


def test_analysis_is_deterministic():
    assert analyse(DRAFT).render() == analyse(DRAFT).render()
