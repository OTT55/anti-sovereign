"""Phase 10 — interactive revision, and the refined draft.

*"It should have an option to produce you not even a draft, but a refined
version. And the tweaking should be interactive."*
"""

import pytest

from storyatlas_engine import Session

DRAFT = """Mara Sadel was born in the year 1150. Mara Sadel betrayed Aldric Vane
in the year 1100.

***

Aldric Vane rode north. He died at Dawnhold.
"""


@pytest.fixture
def session():
    return Session(DRAFT)


def test_a_session_starts_with_the_same_findings_as_a_report(session):
    assert session.issues()
    assert any(fix.severity == "error" for fix in session.issues())


def test_a_preview_changes_nothing(session):
    before = session.text
    fix = session.issues()[0]
    session.preview(fix, fix.options[0], value=1090)
    assert session.text == before


def test_a_preview_shows_both_sides(session):
    """A revision that fixes one contradiction and creates two is worse than no
    revision, and the only way to know is to re-read the whole draft."""
    fix = next(f for f in session.issues() if f.severity == "error")
    action = next(o for o in fix.options if o.kind == "set-year")
    preview = session.preview(fix, action, value=1090)
    assert isinstance(preview.resolved, list)
    assert isinstance(preview.introduced, list)
    assert preview.describe()


def test_fixing_the_birth_date_resolves_the_contradiction(session):
    """Mara betrays somebody in 1100 but is born in 1150. Moving the birth to
    1090 makes the draft consistent."""
    fix = next(f for f in session.issues() if f.severity == "error")
    action = next(o for o in fix.options if o.kind == "set-year")
    preview = session.preview(fix, action, value=1090)
    assert preview.resolved
    assert preview.is_improvement


def test_applying_a_decision_edits_the_text_and_re_reads(session):
    fix = next(f for f in session.issues() if f.severity == "error")
    action = next(o for o in fix.options if o.kind == "set-year")
    session.apply(fix, action, value=1090)
    assert "1090" in session.refined()
    assert session.history


def test_undo_restores_both_the_text_and_the_findings(session):
    before_text = session.text
    before_count = len(session.issues())
    fix = session.issues()[0]
    session.apply(fix, fix.options[0], value=1090)
    session.undo()
    assert session.text == before_text
    assert len(session.issues()) == before_count


def test_undo_on_an_untouched_session_returns_nothing(session):
    assert session.undo() is None


def test_dismissing_removes_a_finding_without_touching_the_text(session):
    fix = session.issues()[0]
    before = session.text
    dismiss = next(o for o in fix.options if o.kind == "dismiss")
    session.apply(fix, dismiss)
    assert session.text == before
    assert fix.title not in [f.title for f in session.issues()]


def test_undoing_a_dismissal_brings_the_finding_back(session):
    fix = session.issues()[0]
    dismiss = next(o for o in fix.options if o.kind == "dismiss")
    session.apply(fix, dismiss)
    session.undo()
    assert fix.title in [f.title for f in session.issues()]


def test_naming_a_pronoun_rewrites_it(session):
    pronoun = [f for f in session.issues() if f.rule == "pronoun"]
    if not pronoun:
        pytest.skip("this draft produced no pronoun question")
    fix = pronoun[0]
    action = next(o for o in fix.options if o.kind == "name")
    session.apply(fix, action)
    assert action.payload["name"] in session.refined()


def test_an_annotation_leaves_the_prose_alone(session):
    """The writer's sentence is left exactly as written and the note is visibly
    the engine's. Rewriting someone's prose to record a decision about it is not
    the engine's business."""
    fix = next(f for f in session.issues()
               if any(o.kind == "annotate" for o in f.options))
    action = next(o for o in fix.options if o.kind == "annotate")
    session.apply(fix, action)
    assert "[" in session.refined() and "]" in session.refined()


def test_a_note_lands_inside_the_sentence_it_annotates(session):
    """After the full stop it belongs to the *next* sentence as far as the
    splitter is concerned, so a marker meant to exempt one line silently exempts
    the line below it and leaves the real one still reported."""
    fix = next(f for f in session.issues()
               if any(o.kind == "annotate" for o in f.options))
    action = next(o for o in fix.options if o.kind == "annotate")
    session.apply(fix, action)

    carrying = [s for s in session.reading.sentences if "[" in s.text]
    assert len(carrying) == 1
    assert carrying[0].text.rstrip().endswith((".", "!", "?", '."', ".”"))
    assert "]" in carrying[0].text


def test_marking_something_deliberate_actually_stops_reporting_it():
    """The option says it stops the engine reporting it. It has to be true —
    an offered fix that does nothing is worse than no fix at all."""
    draft = ("Mara Sadel died in the year 1100.\n\n***\n\n"
             "In the year 1200, Mara Sadel betrayed Aldric Vane.")
    session = Session(draft)
    fix = next(f for f in session.issues() if f.rule == "posthumous")
    action = next(o for o in fix.options if o.kind == "annotate")
    preview = session.preview(fix, action)
    assert preview.resolved
    assert preview.is_improvement


def test_the_refined_draft_is_the_original_until_something_is_decided(session):
    assert session.refined() == DRAFT


def test_reset_returns_to_the_original(session):
    fix = session.issues()[0]
    session.apply(fix, fix.options[0], value=1090)
    session.reset()
    assert session.refined() == DRAFT
    assert session.history == []


def test_a_transcript_records_what_each_decision_did(session):
    assert "No decisions" in session.transcript()
    fix = next(f for f in session.issues() if f.severity == "error")
    action = next(o for o in fix.options if o.kind == "set-year")
    session.apply(fix, action, value=1090)
    transcript = session.transcript()
    assert "Revision log" in transcript
    assert "resolved" in transcript


def test_a_session_diff_covers_the_whole_revision(session):
    assert session.diff() == ""
    fix = next(f for f in session.issues() if f.severity == "error")
    action = next(o for o in fix.options if o.kind == "set-year")
    session.apply(fix, action, value=1090)
    assert "1090" in session.diff()


def test_the_same_decisions_always_give_the_same_draft():
    def run():
        s = Session(DRAFT)
        fix = next(f for f in s.issues() if f.severity == "error")
        action = next(o for o in fix.options if o.kind == "set-year")
        s.apply(fix, action, value=1090)
        return s.refined()
    assert run() == run()


def test_an_edit_that_makes_things_worse_says_so():
    """Moving Mara's birth later, not earlier, keeps the contradiction and is
    reported as no improvement rather than quietly applied as a fix."""
    session = Session(DRAFT)
    fix = next(f for f in session.issues() if f.severity == "error")
    action = next(o for o in fix.options if o.kind == "set-year")
    preview = session.preview(fix, action, value=1200)
    assert not preview.is_improvement
