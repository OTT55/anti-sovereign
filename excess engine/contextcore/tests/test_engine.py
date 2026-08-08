"""End-to-end tests against the real engine, no mocks. No ANTHROPIC_API_KEY is set in this
environment, so ingestion/asking exercise the real, honest extractive/no-graph fallback
paths — the same code path the app falls back to in production when credit runs out.
"""

import pytest

from contextcore_engine.engine import ContextCoreEngine

REPORT_TEXT = """Q3 Financial Summary

Revenue grew twelve percent quarter over quarter, driven primarily by new
enterprise contracts signed in August and September.

Engineering Update

The authentication system rewrite shipped in October, closing out three
long-standing security tickets.

Customer Success

Churn dropped after the onboarding redesign launched, with the biggest
improvement in the first-week retention cohort.
"""


@pytest.fixture
def engine():
    eng = ContextCoreEngine(db_path=":memory:")
    yield eng
    eng.close()


def test_ingest_produces_a_doc_id_and_chunks(engine):
    result = engine.ingest_document("Q3 Report", REPORT_TEXT, extract_entities=False)
    assert result["doc_id"].startswith("CX-")
    assert result["chunk_count"] >= 1


def test_ingest_with_no_extractable_text_returns_none(engine):
    assert engine.ingest_document("Empty", "   \n\n  ") is None


def test_ask_retrieves_the_relevant_chunk_and_falls_back_to_extractive(engine):
    result = engine.ingest_document("Q3 Report", REPORT_TEXT, extract_entities=False)
    answer = engine.ask(result["doc_id"], "what happened to revenue?")
    assert answer.mode == "extractive"  # no API key in this environment
    assert "twelve percent" in answer.answer
    assert answer.confidence["level"] in ("high", "medium", "low", "none")
    assert answer.citations


def test_ask_unrelated_question_yields_no_citations(engine):
    result = engine.ingest_document("Q3 Report", REPORT_TEXT, extract_entities=False)
    answer = engine.ask(result["doc_id"], "zzzblorp nonword gibberish")
    assert answer.citations == []
    assert answer.confidence["level"] == "none"


def test_ingest_without_api_key_skips_extraction_honestly(engine):
    result = engine.ingest_document("Q3 Report", REPORT_TEXT, extract_entities=True)
    assert result["entity_count"] == 0
    assert result["extraction_note"] is not None
    assert "ANTHROPIC_API_KEY" in result["extraction_note"]


def test_graph_for_document_with_no_entities_is_empty(engine):
    result = engine.ingest_document("Q3 Report", REPORT_TEXT, extract_entities=True)
    nodes, edges, svg = engine.graph_for([result["doc_id"]])
    assert nodes == {}
    assert edges == []
    assert svg is None


def test_list_documents_reflects_ingested_docs(engine):
    engine.ingest_document("Q3 Report", REPORT_TEXT, extract_entities=False)
    docs = engine.list_documents()
    assert len(docs) == 1
    assert docs[0]["title"] == "Q3 Report"


def test_ask_collection_pools_multiple_documents(engine):
    engine.ingest_document("Doc A", "The launch date moved to March.", category="planning", extract_entities=False)
    engine.ingest_document("Doc B", "The launch date moved to April instead.", category="planning", extract_entities=False)
    answer = engine.ask_collection("planning", "when is the launch")
    assert answer.citations
    assert all("doc_title" in c for c in answer.citations)
