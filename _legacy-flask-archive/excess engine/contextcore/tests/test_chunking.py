from contextcore_engine.chunking import chunk_text, tokenize


def test_tokenize_drops_stopwords_and_short_tokens():
    toks = tokenize("The quick fox is a runner and it jumps over dogs")
    assert "the" not in toks
    assert "is" not in toks
    assert "a" not in toks
    assert "quick" in toks
    assert "jumps" in toks


def test_chunk_text_respects_paragraph_boundaries():
    text = "Para one is short.\n\nPara two is also short.\n\nPara three closes it out."
    chunks = chunk_text(text, target=1000)
    assert chunks == [text]


def test_chunk_text_splits_when_over_target():
    para_a = "A" * 400
    para_b = "B" * 400
    chunks = chunk_text(f"{para_a}\n\n{para_b}", target=500)
    assert len(chunks) == 2
    assert chunks[0] == para_a
    assert chunks[1] == para_b


def test_chunk_text_splits_long_single_paragraph_on_sentences():
    sentences = " ".join(f"Sentence number {i}." for i in range(40))
    chunks = chunk_text(sentences, target=100)
    assert len(chunks) > 1
    assert all(len(c) <= 120 for c in chunks)  # a little slack for the join
    assert "".join(chunks).replace(" ", "") in sentences.replace(" ", "")


def test_chunk_text_empty_input_returns_no_chunks():
    assert chunk_text("   \n\n  ") == []
