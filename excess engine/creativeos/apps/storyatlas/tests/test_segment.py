"""Sentence and clause segmentation — the stage every later stage depends on."""

from storyatlas_engine.comprehend.segment import split_clauses, split_sentences


def test_plain_sentences_split():
    s = split_sentences("Aldric waited. Mara left. The hall emptied.")
    assert len(s) == 3


def test_an_abbreviation_does_not_end_a_sentence():
    s = split_sentences("Dr. Vane entered the hall.")
    assert len(s) == 1


def test_an_initial_does_not_end_a_sentence():
    s = split_sentences("J. Varo signed the accord.")
    assert len(s) == 1


def test_a_quotation_mark_after_the_stop_stays_attached():
    s = split_sentences('"You are late," she said. He nodded.')
    assert len(s) == 2


def test_sentences_keep_their_source_offsets():
    """Every asserted fact cites the sentence it came from, so a writer can
    always be shown why the engine believes something."""
    text = "Aldric waited. Mara left."
    for sentence in split_sentences(text):
        assert text[sentence.start:sentence.end].strip() == sentence.text


def test_a_conjunction_splits_two_events():
    parts = split_clauses("Aldric died in 1147 and Mara was crowned that same year.")
    assert len(parts) == 2


def test_a_sentence_with_no_conjunction_stays_whole():
    assert len(split_clauses("Aldric died in 1147.")) == 1
