"""Phase 7 — completing the Verification Engine.

Phase 1 detected contradictions. This adds evidence, ambiguity, relationship
validity, and a certainty number that can be explained.
"""

import pytest

from creativeos_engine.graph import ValidWindow
from creativeos_engine.verification import VerificationEngine


@pytest.fixture
def verify(graph):
    return VerificationEngine(graph)


@pytest.fixture
def aldric(graph, space):
    return graph.create_entity(space.id, "character", "Aldric Vane")


# -- evidence --------------------------------------------------------------

def test_a_single_claim_is_backed_by_its_assertion(graph, verify, aldric):
    graph.assert_attribute(aldric.id, "rank", "captain", confidence=0.8)
    evidence = verify.evidence_for(aldric.id)
    assert len(evidence) == 1
    assert evidence[0].value == "captain"
    assert evidence[0].score == 0.8


def test_two_independent_sources_corroborate(graph, verify, aldric):
    """Two documents agreeing is real corroboration: 1 - (0.4 x 0.4) = 0.84."""
    graph.assert_attribute(aldric.id, "rank", "captain",
                           source_kind="manuscript", confidence=0.6)
    graph.assert_attribute(aldric.id, "rank", "captain",
                           source_kind="ledger", confidence=0.6)
    evidence = verify.evidence_for(aldric.id, predicate="rank")[0]
    assert evidence.independent_sources == 2
    assert evidence.score == pytest.approx(0.84, abs=0.001)


def test_repetition_from_one_source_is_not_corroboration(graph, verify, aldric):
    """The same document quoted twice is one claim counted twice. Treating that
    as corroboration is how a rumour becomes a fact."""
    graph.assert_attribute(aldric.id, "rank", "captain",
                           source_kind="manuscript", confidence=0.6)
    graph.assert_attribute(aldric.id, "rank", "captain",
                           source_kind="manuscript", confidence=0.6)
    evidence = verify.evidence_for(aldric.id, predicate="rank")[0]
    assert evidence.independent_sources == 1
    assert evidence.score == 0.6


def test_a_retracted_assertion_stops_being_evidence(graph, verify, aldric):
    a = graph.assert_attribute(aldric.id, "rank", "captain")
    assert verify.evidence_for(aldric.id)
    graph.retract(a.id, reason="wrong")
    assert verify.evidence_for(aldric.id) == []


def test_thin_claims_are_surfaced_as_unsupported(graph, verify, aldric):
    graph.assert_attribute(aldric.id, "rumour", "a traitor", confidence=0.2)
    graph.assert_attribute(aldric.id, "rank", "captain", confidence=0.95)
    unsupported = verify.unsupported_claims(aldric.id, threshold=0.5)
    assert [e.value for e in unsupported] == ["a traitor"]


# -- ambiguity -------------------------------------------------------------

def test_two_entities_sharing_a_name_are_ambiguous(graph, verify, space):
    graph.create_entity(space.id, "character", "Aldric")
    graph.create_entity(space.id, "location", "Aldric")
    found = verify.ambiguities(space.id)
    assert len(found) == 1
    assert len(found[0].candidates) == 2


def test_a_unique_name_is_not_ambiguous(graph, verify, space):
    graph.create_entity(space.id, "character", "Aldric Vane")
    assert verify.ambiguities(space.id) == []


def test_merged_entities_are_no_longer_ambiguous(graph, verify, space):
    """They shared a name because they were the same thing."""
    a = graph.create_entity(space.id, "character", "Aldric")
    b = graph.create_entity(space.id, "character", "Aldric")
    assert verify.ambiguities(space.id)

    graph.merge_entities(a.id, b.id, reason="same person")
    assert verify.ambiguities(space.id) == []


# -- relationship validity -------------------------------------------------

def test_a_relationship_after_a_party_ceased_to_exist_is_invalid(graph, verify, space):
    """Serving under a commander a century after that commander died."""
    commander = graph.create_entity(space.id, "character", "Admiral Locke")
    officer = graph.create_entity(space.id, "character", "Kell Varo")
    graph.assert_attribute(commander.id, "alive", "true", valid=ValidWindow(1000, 1050))
    graph.assert_relationship(officer.id, "served_under", commander.id,
                              valid=ValidWindow(1150, 1160))

    invalid = verify.invalid_relationships(space.id)
    assert invalid
    assert "no longer existed" in invalid[0].reason


def test_a_relationship_before_a_party_existed_is_invalid(graph, verify, space):
    guild = graph.create_entity(space.id, "organization", "The Guild")
    member = graph.create_entity(space.id, "character", "Kell Varo")
    graph.assert_attribute(guild.id, "exists", "true", valid=ValidWindow(1200, None))
    graph.assert_relationship(member.id, "member_of", guild.id,
                              valid=ValidWindow(1100, 1150))

    invalid = verify.invalid_relationships(space.id)
    assert invalid
    assert "did not exist until" in invalid[0].reason


def test_a_relationship_within_both_lifespans_is_valid(graph, verify, space):
    commander = graph.create_entity(space.id, "character", "Admiral Locke")
    officer = graph.create_entity(space.id, "character", "Kell Varo")
    graph.assert_attribute(commander.id, "alive", "true", valid=ValidWindow(1000, 1200))
    graph.assert_relationship(officer.id, "served_under", commander.id,
                              valid=ValidWindow(1100, 1150))

    assert verify.invalid_relationships(space.id) == []


def test_an_undated_relationship_cannot_violate_a_lifespan(graph, verify, space):
    """No temporal claim, nothing to contradict."""
    commander = graph.create_entity(space.id, "character", "Admiral Locke")
    officer = graph.create_entity(space.id, "character", "Kell Varo")
    graph.assert_attribute(commander.id, "alive", "true", valid=ValidWindow(1000, 1050))
    graph.assert_relationship(officer.id, "served_under", commander.id)

    assert verify.invalid_relationships(space.id) == []


# -- the verdict -----------------------------------------------------------

def test_certainty_is_set_by_the_weakest_claim(graph, verify, aldric):
    """A picture is only as sound as its shakiest load-bearing claim."""
    graph.assert_attribute(aldric.id, "rank", "captain", confidence=0.95)
    graph.assert_attribute(aldric.id, "rumour", "a traitor", confidence=0.3)
    assert verify.verify_entity(aldric.id).certainty == 0.3


def test_a_contradiction_caps_certainty_hard(graph, verify, space, aldric):
    graph.assert_attribute(aldric.id, "status", "alive",
                           valid=ValidWindow(0, 400), confidence=1.0)
    graph.assert_attribute(aldric.id, "status", "dead",
                           valid=ValidWindow(300, 600), confidence=1.0)
    verdict = verify.verify_entity(aldric.id)
    assert verdict.contradictions
    assert verdict.certainty <= 0.4


def test_certainty_is_none_when_there_is_nothing_to_judge(verify, aldric):
    assert verify.verify_entity(aldric.id).certainty is None


def test_a_clean_space_reports_clean(graph, verify, space):
    entity = graph.create_entity(space.id, "character", "Aldric Vane")
    graph.assert_attribute(entity.id, "rank", "captain")
    assert verify.verify_space(space.id).is_clean


def test_the_verdict_summarises_every_check(graph, verify, space, aldric):
    graph.assert_attribute(aldric.id, "rank", "captain", confidence=0.9)
    summary = verify.verify_entity(aldric.id).summary()
    assert set(summary) == {
        "evidence", "contradictions", "ambiguities",
        "invalid_relationships", "unsupported", "certainty",
    }


def test_verification_is_deterministic(graph, verify, space, aldric):
    graph.assert_attribute(aldric.id, "rank", "captain", confidence=0.7)
    assert (verify.verify_entity(aldric.id).summary()
            == verify.verify_entity(aldric.id).summary())
