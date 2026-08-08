"""Splitting money so the parts always add up to the whole.

Platform-level, not RightsForge's: royalties, prizes and fees are all the same
arithmetic, and two applications rounding by slightly different rules is how a
payout quietly comes up short.

The property under test is one line: **the shares reconstruct the total,
exactly, for every input.** Everything else is a way of trying to break it.
"""

import pytest

from creativeos_engine.platform import (
    SplitError, from_pounds, split_pence, to_pounds, total_of, validate_split,
)


# -- the property -----------------------------------------------------------

def test_shares_always_reconstruct_the_total():
    """Over a few thousand awkward combinations, not a hand-picked example.

    70/30 of £10.01 is 700.7p and 300.3p; rounding each independently gives
    1001p only by luck, and truncating each loses a penny every time.
    """
    splits = [
        [("a", 70), ("b", 30)],
        [("a", 33), ("b", 33), ("c", 34)],
        [("a", 1), ("b", 99)],
        [("a", 25), ("b", 25), ("c", 25), ("d", 25)],
        [("a", 17), ("b", 41), ("c", 42)],
        [("solo", 100)],
    ]
    for split in splits:
        for amount in range(0, 2000):
            shares = split_pence(amount, split)
            assert total_of(shares) == amount, (amount, split)


def test_no_penny_is_invented_or_lost_on_a_large_sum():
    shares = split_pence(4_500_000, [("a", 33), ("b", 33), ("c", 34)])
    assert total_of(shares) == 4_500_000


def test_the_leftover_goes_to_whoever_lost_the_most():
    """Largest remainder, not first-come. 1p split three ways gives the penny to
    the largest share rather than to whoever happens to be listed first."""
    shares = split_pence(1, [("small", 20), ("large", 80)])
    assert {s.payee: s.pence for s in shares} == {"small": 0, "large": 1}


def test_ties_are_broken_by_position_so_results_are_stable():
    first = split_pence(101, [("a", 50), ("b", 50)])
    second = split_pence(101, [("a", 50), ("b", 50)])
    assert [s.pence for s in first] == [s.pence for s in second]
    assert total_of(first) == 101


def test_shares_come_back_in_the_order_they_were_given():
    shares = split_pence(1000, [("z", 10), ("a", 90)])
    assert [s.payee for s in shares] == ["z", "a"]


# -- refusing what cannot be honoured ---------------------------------------

def test_a_split_that_does_not_reach_a_hundred_is_refused():
    """The app this replaces never checks. A 97% split silently decides that
    somebody absorbs the missing 3%."""
    with pytest.raises(SplitError, match="97%"):
        validate_split([("a", 70), ("b", 27)])


def test_a_split_over_a_hundred_is_refused():
    with pytest.raises(SplitError, match="110%"):
        validate_split([("a", 70), ("b", 40)])


def test_a_duplicate_payee_is_refused():
    with pytest.raises(SplitError, match="twice"):
        validate_split([("OTT", 50), ("ott", 50)])


def test_an_empty_split_is_refused():
    with pytest.raises(SplitError):
        validate_split([])


def test_a_zero_share_is_refused():
    with pytest.raises(SplitError, match="pays nothing"):
        validate_split([("a", 100), ("b", 0)])


def test_a_nameless_payee_is_refused():
    with pytest.raises(SplitError, match="named payee"):
        validate_split([("  ", 50), ("b", 50)])


def test_a_fractional_percentage_is_refused():
    """Allowing 0.5% reintroduces exactly the rounding this module exists to
    eliminate."""
    with pytest.raises(SplitError, match="non-integer"):
        validate_split([("a", 99.5), ("b", 0.5)])


def test_a_float_amount_is_refused():
    with pytest.raises(SplitError, match="integer pence"):
        split_pence(10.5, [("a", 100)])


def test_a_negative_payment_is_refused():
    with pytest.raises(SplitError, match="negative"):
        split_pence(-100, [("a", 100)])


def test_a_boolean_is_not_an_integer_here():
    """`isinstance(True, int)` is True in Python, and a split of `True`% would
    otherwise pass validation as 1%."""
    with pytest.raises(SplitError):
        validate_split([("a", True), ("b", 99)])


# -- the edges --------------------------------------------------------------

def test_pounds_convert_at_the_edge_without_losing_a_penny():
    """£29.99 arrives from JSON as 29.989999999999998; truncating bills a penny
    less than the listed price."""
    assert from_pounds(29.99) == 2999
    assert from_pounds("18000") == 1800000


def test_money_is_only_a_string_at_the_very_edge():
    assert to_pounds(450000) == "£4,500.00"
    assert to_pounds(1) == "£0.01"
