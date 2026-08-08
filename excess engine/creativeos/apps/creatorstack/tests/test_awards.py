"""Dividing a prize so the placings reconstruct the pot exactly."""

import pytest

from creatorstack_engine import AwardError, CreatorStack, allocate


def test_a_single_winner_takes_the_whole_pot():
    shares = allocate(500_000, ["S-1"])
    assert [s.pence for s in shares] == [500_000]


def test_the_placings_always_sum_to_the_prize():
    """A prize fund that does not balance is one somebody will ask about."""
    for pot in range(0, 3000):
        for placings in (["a"], ["a", "b"], ["a", "b", "c"], ["a", "b", "c", "d"]):
            shares = allocate(pot, placings)
            assert sum(s.pence for s in shares) == pot, (pot, placings)


def test_an_awkward_three_way_split_still_balances():
    """1/3 each of £50.00 is 1666.66p, and 'about a third' is not an amount
    anyone can be paid."""
    shares = allocate(5000, ["a", "b", "c"], split=[33, 33, 34])
    assert sum(s.pence for s in shares) == 5000
    assert sorted(s.pence for s in shares) == [1650, 1650, 1700]


def test_an_explicit_split_is_honoured():
    shares = allocate(1000, ["a", "b"], split=[60, 40])
    assert [s.pence for s in shares] == [600, 400]


def test_a_split_that_does_not_reach_a_hundred_is_refused():
    with pytest.raises(Exception, match="90%"):
        allocate(1000, ["a", "b"], split=[60, 30])


def test_a_mismatched_split_is_refused():
    with pytest.raises(AwardError, match="2 shares were given for 3"):
        allocate(1000, ["a", "b", "c"], split=[60, 40])


def test_the_same_entry_cannot_take_two_placings():
    with pytest.raises(AwardError, match="two placings"):
        allocate(1000, ["a", "a"])


def test_no_placings_is_refused():
    with pytest.raises(AwardError, match="at least one placing"):
        allocate(1000, [])


def test_an_unusual_number_of_placings_needs_an_explicit_split():
    """Guessing at how to divide a prize is not the engine's decision to make."""
    with pytest.raises(AwardError, match="No default split for 5"):
        allocate(1000, ["a", "b", "c", "d", "e"])
    assert allocate(1000, ["a", "b", "c", "d", "e"], split=[20] * 5)


def test_an_award_through_the_engine_pays_every_placing():
    stack = CreatorStack()
    brief = stack.post_challenge("nova-films", "Dread", prize_pence=500_000,
                                 deadline=30, now=0)
    ids = [stack.submit(brief.id, who, "pitch", now=5).id
           for who in ("ott", "kestrel", "nova")]
    award = stack.award(brief.id, ids, by="nova-films", now=31)
    assert award.total_pence == 500_000
    assert [s.pence for s in award.shares] == [300_000, 150_000, 50_000]
    assert award.winner == ids[0]


def test_an_award_describes_itself():
    stack = CreatorStack()
    brief = stack.post_challenge("s", "t", prize_pence=1000, deadline=1, now=0)
    entry = stack.submit(brief.id, "c", "pitch", now=1)
    award = stack.award(brief.id, [entry.id], by="s", now=2)
    assert "£10.00" in award.describe()
