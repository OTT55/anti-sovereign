from contextcore_engine.retrieval import TFIDFIndex


CHUNKS = [
    "The quarterly revenue grew by twelve percent driven by enterprise contracts.",
    "Our engineering team shipped the new authentication system in October.",
    "Customer churn dropped after the onboarding redesign launched last quarter.",
    "The marketing budget was reallocated toward organic content in Q3.",
]


def test_search_ranks_relevant_chunk_first():
    index = TFIDFIndex(CHUNKS)
    hits = index.search("what happened to revenue this quarter")
    assert hits, "expected at least one hit"
    top_index, top_score = hits[0]
    assert top_index == 0
    assert top_score > 0


def test_search_returns_nothing_for_unrelated_query():
    index = TFIDFIndex(CHUNKS)
    hits = index.search("zzzblorp nonword gibberish")
    assert hits == []


def test_search_respects_k():
    index = TFIDFIndex(CHUNKS)
    hits = index.search("quarter revenue team budget churn", k=2)
    assert len(hits) <= 2


def test_search_is_deterministic():
    index = TFIDFIndex(CHUNKS)
    a = index.search("engineering authentication system")
    b = index.search("engineering authentication system")
    assert a == b
