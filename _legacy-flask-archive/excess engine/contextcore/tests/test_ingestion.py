"""Phase 2 — the Ingestion Engine, completed.

Whether a document should be ingested at all, and what it is.
"""

from contextcore_engine.ingestion import (
    classify_incoming, content_hash, detect_language, diff_summary,
    extract_metadata, similarity,
)


# -- duplicate detection ----------------------------------------------------

def test_identical_text_hashes_identically():
    assert content_hash("The Accord was signed.") == content_hash("The Accord was signed.")


def test_whitespace_differences_do_not_make_a_new_document():
    """A re-export differing only in line endings is the same document."""
    assert content_hash("The Accord\nwas signed.") == content_hash("The Accord was  signed. ")


def test_different_text_hashes_differently():
    assert content_hash("Signed in 1147.") != content_hash("Signed in 1148.")


def test_an_exact_duplicate_is_caught():
    existing = [{"doc_id": "CX-1", "title": "Accord", "text": "Signed in 1147.",
                 "content_hash": content_hash("Signed in 1147.")}]
    decision = classify_incoming("Accord", "Signed in 1147.", existing)
    assert decision.action == "duplicate"
    assert decision.existing_doc_id == "CX-1"
    assert "CX-1" in decision.reason


# -- version detection ------------------------------------------------------

BASE = ("The Meridian Accord was signed in 1147 by the coastal provinces. "
        "It guaranteed free passage through the Sundered Strait. "
        "Ratification required a two-thirds majority of the assembly.")
EDITED = ("The Meridian Accord was signed in 1147 by the coastal provinces. "
          "It guaranteed free passage through the Sundered Strait for all fleets. "
          "Ratification required a two-thirds majority of the assembly.")


def test_a_lightly_edited_document_is_a_version_not_a_duplicate():
    existing = [{"doc_id": "CX-1", "title": "Accord", "text": BASE,
                 "content_hash": content_hash(BASE)}]
    decision = classify_incoming("Accord", EDITED, existing)
    assert decision.action == "version"
    assert decision.existing_doc_id == "CX-1"
    assert decision.similarity > 0.6


def test_a_different_document_with_the_same_title_is_not_a_version():
    """Title alone would link every document anyone called "Report"."""
    existing = [{"doc_id": "CX-1", "title": "Report", "text": BASE,
                 "content_hash": content_hash(BASE)}]
    decision = classify_incoming(
        "Report", "Entirely unrelated content about shipping tariffs and quotas.",
        existing)
    assert decision.action == "ingest"


def test_similar_text_under_a_different_title_is_not_a_version():
    """Similarity alone would link every contract to every other contract."""
    existing = [{"doc_id": "CX-1", "title": "Accord", "text": BASE,
                 "content_hash": content_hash(BASE)}]
    assert classify_incoming("Treaty", EDITED, existing).action == "ingest"


def test_a_first_document_is_always_new():
    assert classify_incoming("Accord", BASE, []).action == "ingest"


def test_the_decision_explains_itself():
    existing = [{"doc_id": "CX-1", "title": "Accord", "text": BASE,
                 "content_hash": content_hash(BASE)}]
    decision = classify_incoming("Accord", EDITED, existing)
    assert "CX-1" in decision.reason
    assert "%" in decision.reason


# -- similarity -------------------------------------------------------------

def test_identical_text_is_fully_similar():
    assert similarity(BASE, BASE) == 1.0


def test_unrelated_text_is_not_similar():
    assert similarity(BASE, "Shipping tariffs rose sharply last quarter.") < 0.1


def test_similarity_survives_reordering_of_real_paragraphs():
    """Most shingles sit *inside* a paragraph, so moving whole paragraphs
    breaks only the few that straddle the joins."""
    p1 = "The Meridian Accord was signed in 1147 by the coastal provinces after long negotiation."
    p2 = "Ratification required a two-thirds majority of the provincial assembly to take effect."
    p3 = "Military vessels remained subject to inspection at every port along the strait."
    assert similarity(f"{p1} {p2} {p3}", f"{p3} {p1} {p2}") > 0.7


def test_reordering_very_short_sentences_does_not_survive():
    """The honest limit of a 5-word shingle: when sentences are shorter than
    the shingle, nearly every shingle straddles a boundary and reordering
    destroys them. Real documents do not look like this, but it is the
    behaviour, and a version check on terse text will miss."""
    a = "The first sentence. The second sentence. The third sentence."
    b = "The third sentence. The first sentence. The second sentence."
    assert similarity(a, b) < 0.5


# -- language ---------------------------------------------------------------

def test_english_is_detected():
    code, confidence = detect_language(
        "The report of the assembly is that the ruling was in favour of the coast.")
    assert code == "en"
    assert confidence > 0


def test_french_is_detected():
    code, _ = detect_language(
        "Le rapport de l'assemblée est que la décision est en faveur de la côte et des provinces.")
    assert code == "fr"


def test_unknown_is_admitted_rather_than_defaulting_to_english():
    """"We could not tell" and "it is English" are different claims."""
    code, _ = detect_language("zzz qqq xxx vvv")
    assert code == "unknown"


def test_empty_text_is_unknown():
    assert detect_language("") == ("unknown", 0.0)


# -- metadata ---------------------------------------------------------------

def test_metadata_records_what_traces_a_chunk_home():
    meta = extract_metadata("Accord", BASE, filename="accord.pdf",
                            media_type="application/pdf")
    assert meta["filename"] == "accord.pdf"
    assert meta["bytes"] > 0
    assert meta["words"] > 0
    assert meta["language"] == "en"
    assert meta["content_hash"] == content_hash(BASE)


# -- diffing ----------------------------------------------------------------

def test_a_diff_reports_what_changed_in_sentences():
    diff = diff_summary(BASE, EDITED)
    assert diff["added"]
    assert diff["removed"]
    assert diff["unchanged"] >= 2
    assert "for all fleets" in diff["added"][0]


def test_an_unchanged_document_diffs_to_nothing():
    diff = diff_summary(BASE, BASE)
    assert diff["added"] == []
    assert diff["removed"] == []
    assert diff["similarity"] == 1.0
