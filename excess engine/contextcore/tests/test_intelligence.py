"""Phases 8 and 9 — the Intelligence Engine and the Domain Engine."""

import sqlite3

import pytest

from contextcore_engine import domain as domain_module
from contextcore_engine.chunking import chunk_text
from contextcore_engine.intelligence import IntelligenceEngine
from contextcore_engine.memory import MemoryEngine

ACCORD = ("The Meridian Accord was signed in 1147 by the coastal provinces. "
          "It guaranteed free passage through the Sundered Strait.")
TARIFF = ("Shipping tariffs rose sharply across the northern ports last quarter, "
          "prompting a review of harbour dues.")
AMEND = ("The Meridian Accord was signed in 1147 by the coastal provinces. "
         "Military vessels remained subject to inspection at every port.")


def _doc(doc_id, title, text, fields=(), entities=(), language="en"):
    return {"doc_id": doc_id, "title": title, "text": text,
            "chunks": chunk_text(text), "language": language,
            "fields": list(fields), "entities": list(entities)}


@pytest.fixture
def corpus():
    return [
        _doc("CX-1", "Accord", ACCORD, fields=["parties"],
             entities=[{"name": "Acme Corp", "type": "organization"},
                       {"name": "Acme Corporation", "type": "organization"}]),
        _doc("CX-2", "Tariffs", TARIFF),
        _doc("CX-3", "Amendment", AMEND),
    ]


# -- Phase 9: the Domain Engine --------------------------------------------

def test_a_known_domain_is_returned():
    assert domain_module.get("legal").name == "legal"
    assert domain_module.get("FILM").name == "film"


def test_an_unknown_domain_degrades_rather_than_raising():
    """An unrecognised domain should not stop an ingest."""
    assert domain_module.get("underwater-basket-weaving").name == "general"


def test_a_domain_normalises_its_own_synonyms():
    """"claimant" and "plaintiff" stop being two different concepts."""
    legal = domain_module.get("legal")
    assert legal.normalize_term("claimant") == "plaintiff"
    assert legal.normalize_term("complainant") == "plaintiff"


def test_domains_disagree_about_the_same_word():
    assert domain_module.get("film").normalize_term("lead") == "protagonist"
    assert domain_module.get("legal").normalize_term("lead") == "lead"


def test_a_domain_knows_what_a_document_should_contain():
    legal = domain_module.get("legal")
    assert "jurisdiction" in legal.missing_fields(["parties"])
    assert legal.missing_fields(
        ["parties", "effective_date", "jurisdiction", "termination"]) == []


def test_the_same_corpus_audits_differently_under_different_domains():
    """Where domain knowledge earns its place."""
    docs = [{"doc_id": "CX-1", "title": "X", "fields": ["title", "logline",
                                                        "characters", "locations"]}]
    assert domain_module.audit(domain_module.get("film"), docs) == []
    assert domain_module.audit(domain_module.get("legal"), docs)


def test_a_pack_can_be_registered_at_runtime():
    """Adding an industry is writing a pack, not writing code."""
    pack = domain_module.DomainPack("medical", entity_types=("patient", "diagnosis"),
                                    expected_fields=("patient", "diagnosis"))
    domain_module.register(pack)
    assert domain_module.get("medical").name == "medical"


def test_the_general_pack_is_deliberately_thin():
    """A domain claiming to know every corpus knows nothing useful about any."""
    assert domain_module.GENERAL.expected_fields == ()


# -- Phase 8: the Intelligence Engine --------------------------------------

def test_what_exists_counts_the_corpus(corpus):
    exists = IntelligenceEngine(corpus).what_exists()
    assert exists["documents"] == 3
    assert exists["chunks"] >= 3
    assert exists["languages"] == ["en"]


def test_entities_are_counted_after_resolution(corpus):
    """"Acme Corp" and "Acme Corporation" are one entity, not two."""
    assert IntelligenceEngine(corpus).what_exists()["entities"] == 1


def test_what_is_connected_finds_the_overlapping_document(corpus):
    connected = IntelligenceEngine(corpus).what_is_connected("CX-1")
    assert connected
    assert connected[0]["doc_id"] == "CX-3"       # shares the Accord opening


def test_an_unrelated_document_is_not_connected(corpus):
    connected = IntelligenceEngine(corpus).what_is_connected("CX-1")
    assert "CX-2" not in [c["doc_id"] for c in connected]


def test_what_matters_ranks_by_unique_contribution(corpus):
    """Length rewards padding; hit counts reward whatever people search for.
    Unique contribution answers: if this vanished, what would be lost?"""
    ranked = dict(IntelligenceEngine(corpus).what_matters())
    assert ranked["Tariffs"] > ranked["Amendment"]


def test_what_is_missing_uses_the_domain(corpus):
    assert IntelligenceEngine(corpus, domain="legal").what_is_missing()
    assert IntelligenceEngine(corpus, domain="general").what_is_missing() == []


def test_recommendations_are_actionable(corpus):
    for line in IntelligenceEngine(corpus, domain="legal").what_happens_next():
        assert len(line) > 15
        assert line[0].isupper()


def test_an_unresolved_alias_is_recommended_for_confirmation(corpus):
    recommendations = " ".join(IntelligenceEngine(corpus).what_happens_next())
    assert "Acme Corporation" in recommendations


def test_a_non_english_document_prompts_a_retrieval_warning():
    """Retrieval is English-tuned; a French document scoring badly is worth
    knowing about rather than discovering later."""
    corpus = [_doc("CX-1", "Rapport", "Le rapport de l'assemblée", language="fr")]
    assert any("English-tuned" in r
               for r in IntelligenceEngine(corpus).what_happens_next())


# -- coordination ----------------------------------------------------------

def test_context_is_assembled_across_the_whole_corpus(corpus):
    ctx = IntelligenceEngine(corpus).context_for("Sundered Strait")
    assert ctx.passages
    assert any("Strait" in p.text for p in ctx.passages)


def test_one_document_cannot_dominate_assembled_context(corpus):
    ctx = IntelligenceEngine(corpus).context_for("Meridian Accord", per_source_cap=1)
    doc_ids = [p.doc_id for p in ctx.passages]
    assert len(doc_ids) == len(set(doc_ids))


def test_two_documents_can_be_compared_through_the_coordinator(corpus):
    comparison = IntelligenceEngine(corpus).compare(
        "military vessels", "CX-1", "CX-3")
    assert comparison.differs


def test_what_changed_reads_the_memory_engine(corpus):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    memory = MemoryEngine(conn)
    memory.record_version("CX-1", "h1")
    memory.record_version("CX-3", "h3", previous_doc_id="CX-1")

    changed = IntelligenceEngine(corpus).what_changed(memory)
    assert any(c["doc_id"] == "CX-3" and c["versions"] == 2 for c in changed)


def test_without_a_memory_engine_nothing_is_claimed_about_change(corpus):
    assert IntelligenceEngine(corpus).what_changed() == []


# -- the briefing ----------------------------------------------------------

def test_a_briefing_answers_every_question(corpus):
    brief = IntelligenceEngine(corpus, domain="legal").brief()
    assert brief.exists["documents"] == 3
    assert brief.matters
    assert brief.missing
    assert brief.next_up


def test_a_briefing_renders_readably(corpus):
    rendered = IntelligenceEngine(corpus, domain="legal").brief().render()
    assert "Corpus briefing (legal)" in rendered
    assert "What matters" in rendered


def test_a_briefing_summarises_numerically(corpus):
    summary = IntelligenceEngine(corpus, domain="legal").brief().summary()
    assert summary["documents"] == 3
    assert summary["domain"] == "legal"


def test_an_empty_corpus_does_not_crash():
    engine = IntelligenceEngine([])
    assert engine.what_matters() == []
    assert engine.brief().render()


def test_intelligence_is_deterministic(corpus):
    a = IntelligenceEngine(corpus, domain="legal").brief().render()
    b = IntelligenceEngine(corpus, domain="legal").brief().render()
    assert a == b
