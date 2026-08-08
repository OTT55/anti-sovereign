"""FrameVault's Provenance and Reputation engines."""

import pytest

from framevault_engine import (
    Registration, ReputationEngine, content_hash, sign, verify,
)

SECRET = "test-secret"


def _record(**overrides):
    record = {
        "content_hash": content_hash(b"the work itself"),
        "registry_id": "FV-0001",
        "creator": "@ott",
        "created_at": "2026-08-02T10:00:00Z",
        "title": "The Sundered Coast",
        "role": "editor",
        "contributors": "",
        "ai_disclosure": "no generative AI used",
        "source": "camera",
    }
    record.update(overrides)
    return record


# -- signing ---------------------------------------------------------------

def test_a_record_verifies_against_its_own_signature():
    record = _record()
    assert verify(record, sign(record, SECRET), SECRET)


def test_the_same_record_always_signs_identically():
    """Canonical serialisation — otherwise re-serialising in a different key
    order would invalidate a perfectly good signature."""
    assert sign(_record(), SECRET) == sign(_record(), SECRET)


def test_a_different_secret_does_not_verify():
    record = _record()
    assert not verify(record, sign(record, SECRET), "another-secret")


def test_an_empty_signature_does_not_verify():
    assert not verify(_record(), "", SECRET)


@pytest.mark.parametrize("field,value", [
    ("content_hash", content_hash(b"a different work")),
    ("creator", "@someone-else"),
    ("title", "A Different Title"),
    ("role", "director"),
    ("created_at", "2020-01-01T00:00:00Z"),
    ("source", "generated"),
])
def test_tampering_with_any_signed_field_breaks_the_signature(field, value):
    record = _record()
    signature = sign(record, SECRET)
    record[field] = value
    assert not verify(record, signature, SECRET)


def test_tampering_with_the_ai_disclosure_breaks_the_signature():
    """The bug this design exists to prevent. Signing only the file hash meant
    a tampered AI-disclosure still validated — the one field a buyer most needs
    to trust was the one nobody was protecting."""
    record = _record()
    signature = sign(record, SECRET)
    record["ai_disclosure"] = "no generative AI used, honestly"
    assert not verify(record, signature, SECRET)


def test_hashing_the_work_never_requires_the_work_to_travel():
    """Only the hash need ever leave the creator's machine."""
    assert content_hash(b"identical bytes") == content_hash(b"identical bytes")
    assert content_hash(b"one work") != content_hash(b"another work")


def test_a_registration_round_trips_through_its_record():
    registration = Registration(**_record())
    assert verify(registration.as_record(), sign(registration.as_record(), SECRET), SECRET)
    assert "@ott" in registration.describe()


# -- reputation ------------------------------------------------------------

def test_reputation_starts_at_nothing():
    assert ReputationEngine().score("@ott") == 0


def test_paid_work_outweighs_being_cast():
    """Weights are deliberate: each step is harder to obtain and therefore
    better evidence."""
    engine = ReputationEngine()
    engine.record("@ott", "hire.completed", source="filmcrew", event_id="e1")
    engine.record("@sam", "role.cast", source="filmcrew", event_id="e2")
    assert engine.score("@ott") > engine.score("@sam")


def test_a_credit_records_which_application_witnessed_it():
    engine = ReputationEngine()
    engine.record("@ott", "hire.completed", source="filmcrew", event_id="e1")
    assert engine.sources_for("@ott") == ["filmcrew"]


def test_two_applications_corroborating_is_visible():
    engine = ReputationEngine()
    engine.record("@ott", "hire.completed", source="filmcrew", event_id="e1")
    engine.record("@ott", "asset.licensed", source="rightsforge", event_id="e2")
    assert engine.sources_for("@ott") == ["filmcrew", "rightsforge"]


def test_the_same_event_credits_only_once():
    engine = ReputationEngine()
    engine.record("@ott", "hire.completed", source="filmcrew", event_id="e1")
    engine.record("@ott", "hire.completed", source="filmcrew", event_id="e1")
    assert engine.score("@ott") == 3.0


def test_distinct_events_of_the_same_kind_both_count():
    engine = ReputationEngine()
    engine.record("@ott", "hire.completed", source="filmcrew", event_id="e1")
    engine.record("@ott", "hire.completed", source="filmcrew", event_id="e2")
    assert engine.score("@ott") == 6.0


def test_the_score_can_be_taken_apart():
    engine = ReputationEngine()
    engine.record("@ott", "hire.completed", source="filmcrew", event_id="e1")
    engine.record("@ott", "role.cast", source="filmcrew", event_id="e2")
    breakdown = engine.breakdown("@ott")
    assert breakdown["hire.completed"]["weight"] == 3.0
    assert breakdown["role.cast"]["count"] == 1


def test_an_unknown_event_kind_still_credits_something_small():
    engine = ReputationEngine()
    engine.record("@ott", "something.new", source="future-app", event_id="e1")
    assert engine.score("@ott") == 0.5


def test_reputation_cannot_be_self_asserted():
    """A résumé is a claim; a paid contract is evidence. There is deliberately
    no method for the first."""
    engine = ReputationEngine()
    assert not hasattr(engine, "add_claim")
    assert not hasattr(engine, "assert_credit")


def test_the_leaderboard_ranks_by_score():
    engine = ReputationEngine()
    engine.record("@ott", "hire.completed", source="filmcrew", event_id="e1")
    engine.record("@sam", "role.cast", source="filmcrew", event_id="e2")
    assert [name for name, _ in engine.leaderboard()] == ["@ott", "@sam"]


def test_a_profile_summarises_everything():
    engine = ReputationEngine()
    engine.record("@ott", "hire.completed", source="filmcrew", event_id="e1")
    profile = engine.profile("@ott")
    assert profile["score"] == 3.0
    assert profile["credits"] == 1
    assert profile["sources"] == ["filmcrew"]
