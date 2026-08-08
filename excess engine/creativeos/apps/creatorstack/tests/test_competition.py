"""Challenges, submissions, and the rules that make a result defensible."""

import pytest

from creatorstack_engine import AwardError, CompetitionError, CreatorStack


class FakeBus:
    def __init__(self):
        self.published = []

    def publish(self, space_id, kind, subject_id, payload, source=""):
        self.published.append({"kind": kind, "subject": subject_id,
                               "payload": payload})
        return len(self.published)

    def kinds(self):
        return [e["kind"] for e in self.published]


@pytest.fixture
def stack():
    return CreatorStack(bus=FakeBus())


@pytest.fixture
def brief(stack):
    return stack.post_challenge("nova-films", "60 seconds of dread",
                                prize_pence=500_000, deadline=30, now=0)


# -- the deadline is computed, not stored -----------------------------------

def test_the_phase_follows_the_clock(stack, brief):
    """Nothing runs at midnight, and there is no job to forget."""
    assert stack.phase(brief.id, now=10) == "open"
    assert stack.phase(brief.id, now=30) == "open"     # the deadline itself
    assert stack.phase(brief.id, now=31) == "judging"


def test_a_late_entry_is_refused(stack, brief):
    """The app stores `submit_deadline` and never compares it to anything, so a
    submission a week late is accepted as long as nobody flipped the status.
    A competition that accepted a late entry and then awarded a prize can be
    challenged by everyone who made the deadline."""
    stack.submit(brief.id, "ott", "In time", now=29)
    with pytest.raises(CompetitionError, match="closed at 30"):
        stack.submit(brief.id, "kestrel", "Too late", now=31)


def test_a_challenge_without_a_deadline_is_refused(stack):
    with pytest.raises(CompetitionError, match="needs a deadline"):
        stack.post_challenge("nova-films", "Open-ended", prize_pence=1000)


def test_a_submission_without_a_time_is_refused(stack, brief):
    """It could not be checked against the deadline, so it must not be taken."""
    with pytest.raises(CompetitionError, match="needs a time"):
        stack.submit(brief.id, "ott", "When?")


# -- eligibility ------------------------------------------------------------

def test_a_sponsor_cannot_enter_their_own_challenge(stack, brief):
    with pytest.raises(CompetitionError, match="cannot enter their own"):
        stack.submit(brief.id, "nova-films", "Mine", now=5)


def test_one_entry_per_creator(stack, brief):
    stack.submit(brief.id, "ott", "First", now=5)
    with pytest.raises(CompetitionError, match="already entered"):
        stack.submit(brief.id, "ott", "Second", now=6)


def test_an_empty_submission_is_refused(stack, brief):
    with pytest.raises(CompetitionError, match="pitch or a file"):
        stack.submit(brief.id, "ott", "   ", now=5)


def test_an_unknown_challenge_is_refused(stack):
    with pytest.raises(CompetitionError, match="Unknown challenge"):
        stack.submit("nope", "ott", "Hello", now=1)


# -- a submission is fixed once it is in ------------------------------------

def test_a_submission_carries_a_content_hash(stack, brief):
    entry = stack.submit(brief.id, "ott", "A corridor.", data=b"film-bytes", now=5)
    assert len(entry.hash) == 64
    assert stack.verify(entry.id, b"film-bytes")


def test_an_edited_file_no_longer_matches(stack, brief):
    """"The entry I judged is the entry they sent" has to be checkable without
    taking anyone's word for it."""
    entry = stack.submit(brief.id, "ott", "A corridor.", data=b"film-bytes", now=5)
    assert not stack.verify(entry.id, b"film-bytes-edited")


def test_identical_content_hashes_identically(stack, brief):
    first = stack.submit(brief.id, "ott", "x", data=b"same", now=5)
    second = stack.submit(brief.id, "kestrel", "y", data=b"same", now=5)
    assert first.hash == second.hash


# -- awarding ---------------------------------------------------------------

def test_only_the_sponsor_can_award(stack, brief):
    entry = stack.submit(brief.id, "ott", "A corridor.", now=5)
    with pytest.raises(AwardError, match="Only nova-films"):
        stack.award(brief.id, [entry.id], by="ott", now=31)


def test_a_challenge_cannot_be_awarded_while_still_open(stack, brief):
    """Judging a field that is not yet complete."""
    entry = stack.submit(brief.id, "ott", "A corridor.", now=5)
    with pytest.raises(AwardError, match="still open"):
        stack.award(brief.id, [entry.id], by="nova-films", now=10)


def test_a_challenge_cannot_be_awarded_twice(stack, brief):
    entry = stack.submit(brief.id, "ott", "A corridor.", now=5)
    stack.award(brief.id, [entry.id], by="nova-films", now=31)
    with pytest.raises(AwardError, match="already been awarded"):
        stack.award(brief.id, [entry.id], by="nova-films", now=32)


def test_an_entry_from_another_challenge_cannot_win(stack, brief):
    other = stack.post_challenge("kestrel", "Other", prize_pence=100,
                                 deadline=30, now=0)
    outsider = stack.submit(other.id, "ott", "Elsewhere", now=5)
    stack.submit(brief.id, "nova", "Here", now=5)
    with pytest.raises(AwardError, match="was not submitted"):
        stack.award(brief.id, [outsider.id], by="nova-films", now=31)


def test_an_empty_challenge_cannot_be_awarded(stack, brief):
    with pytest.raises(AwardError, match="Nothing was submitted"):
        stack.award(brief.id, [], by="nova-films", now=31)


def test_awarding_moves_the_phase(stack, brief):
    entry = stack.submit(brief.id, "ott", "A corridor.", now=5)
    stack.award(brief.id, [entry.id], by="nova-films", now=31)
    assert stack.phase(brief.id, now=31) == "awarded"
    assert stack.winner_of(brief.id) == entry.id


def test_the_award_exists_before_the_event_is_published(stack, brief):
    """A listener reacting to `challenge.won` must not arrive before there is a
    winner to ask about."""
    entry = stack.submit(brief.id, "ott", "A corridor.", now=5)
    seen = {}
    original = stack.bus.publish

    def spy(space_id, kind, subject_id, payload, source=""):
        if kind == "challenge.won":
            seen["winner"] = stack.winner_of(brief.id)
        return original(space_id, kind, subject_id, payload, source)

    stack.bus.publish = spy
    stack.award(brief.id, [entry.id], by="nova-films", now=31)
    assert seen["winner"] == entry.id


def test_every_placing_gets_its_own_event(stack, brief):
    ids = [stack.submit(brief.id, who, "pitch", now=5).id
           for who in ("ott", "kestrel", "nova")]
    stack.award(brief.id, ids, by="nova-films", now=31)
    won = [e for e in stack.bus.published if e["kind"] == "challenge.won"]
    assert [e["payload"]["placing"] for e in won] == [1, 2, 3]
    assert sum(e["payload"]["amount_pence"] for e in won) == 500_000


# -- boundaries -------------------------------------------------------------

def test_the_engine_runs_without_a_bus(brief):
    stack = CreatorStack()
    challenge = stack.post_challenge("s", "t", prize_pence=100, deadline=10, now=0)
    entry = stack.submit(challenge.id, "c", "pitch", now=1)
    assert stack.award(challenge.id, [entry.id], by="s", now=11).winner == entry.id


def test_the_engine_imports_nothing_from_a_sibling_application():
    """Vertical dependencies are allowed; horizontal ones are not."""
    import ast
    import pathlib

    package = pathlib.Path(__file__).resolve().parents[1] / "src" / "creatorstack_engine"
    siblings = ("storyatlas_engine", "framevault_engine", "filmcrew_engine",
                "rightsforge_engine", "studio_engine")
    for module in package.glob("*.py"):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                assert not name.startswith(siblings), f"{module.name} imports {name}"
