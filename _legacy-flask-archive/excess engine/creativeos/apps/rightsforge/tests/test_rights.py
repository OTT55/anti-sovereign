"""The rights ledger: scope × term × exclusivity, and the one collision rule.

> Two grants collide when their scopes overlap **and** their terms overlap
> **and** at least one of them is exclusive.
"""

import pytest

from rightsforge_engine import Grant, Ledger, RightsError, Scope, Term


def grant(work="W1", holder="buyer", right="film", territory="*", medium="*",
          starts=2026, ends=2030, kind="exclusive-license", exclusive=None):
    return Grant(work, holder, Scope(right, territory, medium),
                 Term(starts, ends), kind=kind, exclusive=exclusive)


# -- scope ------------------------------------------------------------------

def test_the_same_right_in_different_territories_does_not_collide():
    """Territory-by-territory selling is how the business works. A model that
    cannot express it cannot sell film rights to two countries."""
    ledger = Ledger()
    ledger.record(grant(territory="uk"))
    ledger.record(grant(territory="france", holder="other"))
    assert len(ledger.grants) == 2


def test_different_rights_in_the_same_territory_do_not_collide():
    ledger = Ledger()
    ledger.record(grant(right="film", territory="uk"))
    ledger.record(grant(right="stage", territory="uk", holder="other"))
    assert len(ledger.grants) == 2


def test_worldwide_overlaps_every_territory():
    assert Scope("film", "*").overlaps(Scope("film", "uk"))
    assert Scope("film", "uk").overlaps(Scope("film", "*"))


def test_a_grant_must_name_a_right():
    with pytest.raises(RightsError, match="which right"):
        Scope("")


def test_scope_comparison_ignores_case_and_spacing():
    assert Scope("Film", " UK ") == Scope("film", "uk")


# -- exclusivity ------------------------------------------------------------

def test_two_non_exclusive_licences_never_collide():
    """Which is exactly why an asset sells a thousand times and a film option
    does not sell twice."""
    ledger = Ledger()
    for i in range(5):
        ledger.record(grant(kind="license", holder=f"buyer{i}"))
    assert len(ledger.grants) == 5


def test_an_exclusive_grant_blocks_an_overlapping_one():
    ledger = Ledger()
    ledger.record(grant(territory="*"))
    with pytest.raises(RightsError, match="exclusive"):
        ledger.record(grant(territory="uk", holder="other"))


def test_an_exclusive_grant_blocks_even_a_non_exclusive_one():
    ledger = Ledger()
    ledger.record(grant(kind="exclusive-license"))
    with pytest.raises(RightsError):
        ledger.record(grant(kind="license", holder="other"))


def test_the_conflict_names_the_exclusive_side():
    """The part a seller disputes."""
    ledger = Ledger()
    ledger.record(grant(holder="atlas-films"))
    conflicts = ledger.check(grant(holder="rival", kind="license"))
    assert conflicts
    assert "atlas-films" in conflicts[0].reason


# -- terms: the part the app cannot express ---------------------------------

def test_grants_in_different_periods_do_not_collide():
    ledger = Ledger()
    ledger.record(grant(starts=2020, ends=2024))
    ledger.record(grant(starts=2025, ends=2029, holder="other"))
    assert len(ledger.grants) == 2


def test_a_lapsed_option_frees_the_work():
    """A `status` column has no room for *until when*, so an option locks a work
    permanently. A term does not — nothing has to run for the rights to come
    back, the date simply passes."""
    ledger = Ledger()
    ledger.record(grant(kind="option", starts=2026, ends=2027))
    assert not ledger.is_available("W1", Scope("film"), Term(2026, 2027))
    assert ledger.is_available("W1", Scope("film"), Term(2028, 2029))


def test_an_option_without_an_end_is_refused():
    """An option that never lapses is an assignment with a smaller price tag."""
    with pytest.raises(RightsError, match="never lapses"):
        Grant("W1", "b", Scope("film"), Term(2026, None), kind="option")


def test_a_purchase_may_be_perpetual():
    assert Grant("W1", "b", Scope("film"), Term(2026, None),
                 kind="purchase").term.is_perpetual


def test_a_perpetual_grant_blocks_everything_after_it():
    ledger = Ledger()
    ledger.record(grant(kind="purchase", starts=2026, ends=None))
    assert not ledger.is_available("W1", Scope("film"), Term(2200, 2201))


def test_a_term_cannot_end_before_it_starts():
    with pytest.raises(RightsError, match="before it starts"):
        Term(2030, 2026)


def test_terms_that_merely_touch_do_overlap():
    assert Term(2020, 2025).overlaps(Term(2025, 2030))
    assert not Term(2020, 2024).overlaps(Term(2025, 2030))


# -- reading the ledger -----------------------------------------------------

def test_live_at_excludes_what_has_lapsed():
    ledger = Ledger()
    ledger.record(grant(kind="option", starts=2026, ends=2027))
    assert len(ledger.live_at("W1", 2026)) == 1
    assert ledger.live_at("W1", 2030) == []


def test_lapsed_lists_rights_that_reverted():
    """The list the app cannot produce at all — a status field has no way to
    represent *used to be optioned*."""
    ledger = Ledger()
    ledger.record(grant(kind="option", starts=2026, ends=2027))
    assert ledger.lapsed("W1", 2030)
    assert ledger.lapsed("W1", 2026) == []


def test_holder_of_answers_who_owns_this_right_now():
    ledger = Ledger()
    ledger.record(grant(holder="atlas-films", territory="uk"))
    assert ledger.holder_of("W1", Scope("film", "uk"), 2027).holder == "atlas-films"
    assert ledger.holder_of("W1", Scope("film", "uk"), 2040) is None
    assert ledger.holder_of("W1", Scope("stage", "uk"), 2027) is None


def test_grants_against_other_works_never_interfere():
    ledger = Ledger()
    ledger.record(grant(work="W1"))
    ledger.record(grant(work="W2"))
    assert len(ledger.for_work("W1")) == 1


def test_check_does_not_record():
    """An application must be able to *offer* a deal without committing to it."""
    ledger = Ledger()
    ledger.check(grant())
    assert ledger.grants == []


def test_every_recorded_grant_gets_an_id():
    ledger = Ledger()
    first = ledger.record(grant())
    second = ledger.record(grant(work="W2"))
    assert first.grant_id != second.grant_id
    assert first.grant_id.startswith("RF-")


def test_a_timeline_is_in_start_order():
    ledger = Ledger()
    ledger.record(grant(kind="option", starts=2030, ends=2031, territory="uk"))
    ledger.record(grant(kind="option", starts=2026, ends=2027, territory="uk"))
    assert [g.term.starts for g in ledger.timeline("W1")] == [2026, 2030]


def test_an_unknown_deal_kind_is_refused():
    with pytest.raises(RightsError, match="Unknown deal kind"):
        Grant("W1", "b", Scope("film"), Term(2026, 2030), kind="rental")
