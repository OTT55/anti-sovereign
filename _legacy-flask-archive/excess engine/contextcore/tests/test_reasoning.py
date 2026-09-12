"""Phases 5–7 — Context, Reasoning and Verification over a corpus."""

from contextcore_engine.chunking import chunk_text
from contextcore_engine.reasoning import (
    Passage, ReasoningPath, ambiguous_terms, assemble, compare_documents,
    trace, verify_answer,
)

V1 = ("The Meridian Accord was signed in 1147 by the coastal provinces. "
      "It guaranteed free passage through the Sundered Strait for all signatory fleets. "
      "Ratification required a two-thirds majority of the provincial assembly.")

V2 = ("The Meridian Accord was signed in 1147 by the coastal provinces. "
      "It guaranteed free passage through the Sundered Strait for all signatory fleets. "
      "Military vessels remained subject to inspection at every port. "
      "Ratification required a simple majority of the provincial assembly.")


def _passages(*specs):
    return [Passage(text, doc_id, doc_id, i, score)
            for i, (text, doc_id, score) in enumerate(specs)]


# -- Phase 5: context assembly ---------------------------------------------

def test_passages_are_kept_best_first():
    ctx = assemble("q", _passages(("low", "A", 0.1), ("high", "B", 0.9)))
    assert ctx.passages[0].text == "high"


def test_a_budget_drops_the_weakest():
    ctx = assemble("q", _passages(("a" * 60, "A", 0.9), ("b" * 60, "B", 0.1)), budget=70)
    assert len(ctx.passages) == 1
    assert ctx.dropped


def test_a_generous_budget_drops_nothing():
    ctx = assemble("q", _passages(("a", "A", 0.9), ("b", "B", 0.1)), budget=10000)
    assert ctx.dropped == []


def test_one_document_cannot_crowd_out_every_other_source():
    """An answer drawn from one document dressed up as a corpus-wide finding
    is misleading — the spread of agreement is part of the evidence."""
    hogging = _passages(("x", "A", 0.9), ("y", "A", 0.8), ("z", "A", 0.7),
                        ("w", "B", 0.1))
    ctx = assemble("q", hogging, per_source_cap=2)
    assert sum(1 for p in ctx.passages if p.doc_id == "A") == 2
    assert any(p.doc_id == "B" for p in ctx.passages)


def test_every_passage_can_cite_itself():
    ctx = assemble("q", _passages(("text", "A", 0.5)))
    assert "chunk 1" in ctx.passages[0].cite()


def test_rendering_says_what_was_omitted():
    ctx = assemble("q", _passages(("a" * 60, "A", 0.9), ("b" * 60, "B", 0.1)), budget=70)
    assert "omitted for space" in ctx.render()


def test_the_summary_counts_sources():
    ctx = assemble("q", _passages(("a", "A", 0.9), ("b", "B", 0.5)))
    assert ctx.summary()["sources"] == 2


# -- Phase 6: multi-hop reasoning ------------------------------------------

def test_comparing_two_versions_finds_what_changed():
    """The question no single passage contains."""
    c = compare_documents("What majority did ratification require?",
                          "V1", V1, "V2", V2)
    assert c.differs
    joined = " ".join(c.only_right)
    assert "simple majority" in joined


def test_identical_documents_do_not_differ():
    c = compare_documents("ratification", "V1", V1, "V1 copy", V1)
    assert not c.differs
    assert c.agreement == 1.0


def test_a_comparison_explains_itself():
    c = compare_documents("majority", "V1", V1, "V2", V2)
    assert "V1" in c.describe() and "V2" in c.describe()
    assert "Only in" in c.render()


def test_a_trace_follows_the_question_across_documents():
    corpus = [
        {"doc_id": "A", "title": "Accord", "chunks": chunk_text(V1)},
        {"doc_id": "B", "title": "Amendment", "chunks": chunk_text(V2)},
    ]
    path = trace("Sundered Strait passage", corpus, hops=2)
    assert path
    assert path[0]["hop"] == 1
    assert path[0]["passages"]


def test_a_later_hop_uses_the_previous_best_passage_as_its_query():
    """What makes it multi-hop rather than a wider single search."""
    corpus = [
        {"doc_id": "A", "title": "Accord", "chunks": chunk_text(V1)},
        {"doc_id": "B", "title": "Amendment", "chunks": chunk_text(V2)},
    ]
    path = trace("ratification majority", corpus, hops=2)
    if len(path) > 1:
        assert path[1]["query"] != path[0]["query"]


def test_a_trace_over_an_empty_corpus_returns_nothing():
    assert trace("anything", []) == []


def test_a_passage_is_never_returned_twice_in_one_trace():
    corpus = [{"doc_id": "A", "title": "Accord", "chunks": chunk_text(V1)}]
    path = trace("Accord", corpus, hops=3)
    seen = [p.text for hop in path for p in hop["passages"]]
    assert len(seen) == len(set(seen))


# -- Phase 7: verification --------------------------------------------------

def test_an_answer_drawn_from_the_passages_is_grounded():
    passages = _passages(("Ratification required a two-thirds majority.", "A", 0.9))
    result = verify_answer("majority?", passages,
                           "Ratification required a two-thirds majority.")
    assert result["grounded"]
    assert result["overlap"] > 0.5


def test_an_answer_resting_on_nothing_is_caught():
    """The failure that matters most for a citing system: plausible, but
    supported by nothing retrieved."""
    passages = _passages(("Ratification required a two-thirds majority.", "A", 0.9))
    result = verify_answer("majority?", passages,
                           "Shipping tariffs rose sharply throughout the period.")
    assert not result["grounded"]
    assert "not be supported" in result["note"]


def test_no_passages_means_ungrounded():
    result = verify_answer("anything", [], "A confident answer.")
    assert not result["grounded"]
    assert "rests on nothing" in result["note"]


def test_verification_records_a_reasoning_path():
    """The difference between an answer a reader can audit and one they must
    trust."""
    passages = _passages(("Ratification required a two-thirds majority.", "A", 0.9))
    result = verify_answer("majority?", passages, "A two-thirds majority.")
    assert len(result["path"]) >= 2
    rendered = result["path"].render()
    assert "retrieve" in rendered and "compare" in rendered


def test_unrelated_passages_flag_the_question_as_ambiguous():
    """Nothing disagrees — the question is unclear."""
    passages = _passages(
        ("The Meridian Accord governs shipping through the strait.", "A", 0.5),
        ("The Aldermere Accord concerns grazing rights in the northern valleys.", "B", 0.5),
    )
    assert ambiguous_terms("tell me about the Accord", passages)


def test_passages_that_agree_are_not_ambiguous():
    passages = _passages(
        ("Ratification required a two-thirds majority of the assembly.", "A", 0.5),
        ("Ratification required a two-thirds majority of the assembly.", "B", 0.5),
    )
    assert ambiguous_terms("ratification", passages) == []


def test_a_reasoning_path_renders_in_order():
    path = ReasoningPath().add("retrieve", "4 passages").add("compare", "against answer")
    rendered = path.render()
    assert rendered.index("1.") < rendered.index("2.")


def test_verification_is_deterministic():
    passages = _passages(("Ratification required a two-thirds majority.", "A", 0.9))
    a = verify_answer("majority?", passages, "A two-thirds majority.")
    b = verify_answer("majority?", passages, "A two-thirds majority.")
    assert a["overlap"] == b["overlap"]
