"""Voting, and how to tell a signal from a brigade."""

import pytest

from creatorstack_engine import Ballot, BallotError, CreatorStack


@pytest.fixture
def stack():
    return CreatorStack()


@pytest.fixture
def brief(stack):
    return stack.post_challenge("nova-films", "60 seconds of dread",
                                prize_pence=500_000, deadline=30, now=0)


@pytest.fixture
def entries(stack, brief):
    return [stack.submit(brief.id, who, f"{who}'s pitch", now=5)
            for who in ("ott", "kestrel", "nova")]


@pytest.fixture
def ballot(brief):
    return Ballot(brief.id)


# -- the two checks the app never makes -------------------------------------

def test_a_creator_cannot_vote_for_their_own_entry(ballot, entries):
    """Votes are the signal the sponsor judges on. A self-vote is a thumb on the
    scale, and nothing in the app checks."""
    with pytest.raises(BallotError, match="own entry"):
        ballot.cast(entries[0], voter="ott")


def test_the_sponsor_cannot_vote(ballot, entries):
    with pytest.raises(BallotError, match="sponsor cannot vote"):
        ballot.cast(entries[0], voter="nova-films", sponsor="nova-films")


# -- one vote per identity --------------------------------------------------

def test_one_vote_per_identity_per_entry(ballot, entries):
    ballot.cast(entries[0], voter="viewer")
    with pytest.raises(BallotError, match="already voted"):
        ballot.cast(entries[0], voter="viewer")


def test_a_voter_may_support_several_entries(ballot, entries):
    ballot.cast(entries[0], voter="viewer")
    ballot.cast(entries[1], voter="viewer")
    assert ballot.count(entries[0].id) == 1
    assert ballot.count(entries[1].id) == 1


def test_a_vote_can_be_withdrawn(ballot, entries):
    ballot.cast(entries[0], voter="viewer")
    assert ballot.withdraw(entries[0].id, "viewer")
    assert ballot.count(entries[0].id) == 0
    assert not ballot.withdraw(entries[0].id, "viewer")


def test_a_vote_needs_a_voter(ballot, entries):
    with pytest.raises(BallotError, match="needs a voter"):
        ballot.cast(entries[0], voter="")


# -- telling support from coordination --------------------------------------

def test_a_raw_count_cannot_tell_them_apart(ballot, entries):
    """Twenty votes from twenty people who also voted elsewhere is a result.
    Twenty from accounts that voted for nothing else is a brigade. Both are 20."""
    for i in range(20):
        ballot.cast(entries[0], voter=f"sock{i}")
    for i in range(20):
        ballot.cast(entries[1], voter=f"real{i}")
        ballot.cast(entries[2], voter=f"real{i}")

    tallies = {t.submission_id: t for t in ballot.tally(entries)}
    assert tallies[entries[0].id].votes == tallies[entries[1].id].votes == 20
    assert tallies[entries[0].id].concentration == 1.0
    assert tallies[entries[1].id].concentration == 0.0


def test_concentrated_support_is_reported(ballot, entries):
    for i in range(10):
        ballot.cast(entries[0], voter=f"sock{i}")
    findings = ballot.integrity(entries)
    assert any(f["signal"] == "concentrated-support" for f in findings)
    assert findings[0]["submission"] == entries[0].id


def test_ordinary_support_is_not_reported(ballot, entries):
    for i in range(10):
        ballot.cast(entries[0], voter=f"viewer{i}")
        ballot.cast(entries[1], voter=f"viewer{i}")
    assert ballot.integrity(entries) == []


def test_the_engine_reports_rather_than_discounts(ballot, entries):
    """Disqualifying somebody's votes is an accusation, and an engine that makes
    it silently is one nobody can argue with. The count is untouched; the
    evidence sits beside it."""
    for i in range(10):
        ballot.cast(entries[0], voter=f"sock{i}")
    assert ballot.count(entries[0].id) == 10
    assert ballot.integrity(entries)


def test_findings_cite_their_numbers(ballot, entries):
    for i in range(10):
        ballot.cast(entries[0], voter=f"sock{i}")
    finding = ballot.integrity(entries)[0]
    assert "10 of 10" in finding["detail"]
    assert finding["concentration"] == 1.0


# -- ranking ----------------------------------------------------------------

def test_the_tally_is_ordered_by_raw_votes(ballot, entries):
    for i in range(3):
        ballot.cast(entries[1], voter=f"v{i}")
    ballot.cast(entries[0], voter="w")
    assert [t.submission_id for t in ballot.tally(entries)][0] == entries[1].id


def test_ranking_is_never_reordered_by_trustworthiness(ballot, entries):
    """Reordering would hide the disagreement between "most votes" and "most
    credible votes", and that disagreement is the whole point."""
    for i in range(10):
        ballot.cast(entries[0], voter=f"sock{i}")
    for i in range(3):
        ballot.cast(entries[1], voter=f"real{i}")
        ballot.cast(entries[2], voter=f"real{i}")
    assert ballot.tally(entries)[0].submission_id == entries[0].id


def test_a_tie_has_no_leader(ballot, entries):
    """There is no honest way to break it, and quietly picking the lower id is a
    result decided by insertion order."""
    ballot.cast(entries[0], voter="a")
    ballot.cast(entries[1], voter="b")
    assert ballot.leader(entries) is None


def test_an_empty_ballot_has_no_leader(ballot, entries):
    assert ballot.leader(entries) is None


def test_a_clear_leader_is_named(ballot, entries):
    ballot.cast(entries[0], voter="a")
    ballot.cast(entries[0], voter="b")
    ballot.cast(entries[1], voter="c")
    assert ballot.leader(entries).submission_id == entries[0].id


def test_the_summary_counts_distinct_voters(ballot, entries):
    ballot.cast(entries[0], voter="a")
    ballot.cast(entries[1], voter="a")
    ballot.cast(entries[1], voter="b")
    assert ballot.summary() == {"submissions_voted_on": 2, "votes": 3, "voters": 2}
