"""Phase 1 — the public interface.

The point of an explicit interface is that callers stop coupling themselves to
the package's internal layout. These tests are what make that promise real: if
a module moves, they still pass; if the *interface* changes, they fail.
"""

import contextcore_engine as cc


def test_every_constitutional_engine_is_reachable_from_the_top_level():
    """One import gets you all eight. No reaching into submodules."""
    for name in (
        "classify_incoming",        # 1 ingestion
        "resolve", "Ontology",      # 2 knowledge
        "assemble",                 # 3 context
        "MemoryEngine",             # 4 memory
        "compare_documents",        # 5 reasoning
        "verify_answer",            # 6 verification
        "IntelligenceEngine",       # 7 intelligence
        "domain",                   # 8 domain
    ):
        assert hasattr(cc, name), name


def test_the_engine_itself_is_the_headline_export():
    assert cc.ContextCoreEngine is not None
    assert cc.AskResult is not None


def test_everything_advertised_actually_exists():
    """A stale __all__ is worse than none — it promises what is not there."""
    missing = [name for name in cc.__all__ if not hasattr(cc, name)]
    assert missing == []


def test_the_interface_works_without_touching_submodules():
    """A caller should never need to know which file something lives in."""
    decision = cc.classify_incoming("Report", "Some text about the assembly.", [])
    assert decision.is_new

    clusters = cc.resolve([{"name": "Acme Corp", "type": "organization"},
                           {"name": "Acme Corporation", "type": "organization"}])
    assert len(clusters) == 1

    assert cc.domain.get("legal").name == "legal"


def test_the_engine_runs_end_to_end_from_the_public_api():
    engine = cc.ContextCoreEngine(db_path=":memory:")
    result = engine.ingest_document(
        "Accord",
        "The Meridian Accord was signed in 1147.\n\n"
        "Ratification required a two-thirds majority of the assembly.",
        extract_entities=False)
    assert result["chunk_count"] >= 1

    answer = engine.ask(result["doc_id"], "what majority was required?")
    assert "two-thirds" in answer.answer
    engine.close()
