"""The one seam where a local model is allowed near the engine, and its fence.

These tests are mostly about what the seam *refuses* to do. The engine's whole
claim is that its conclusions are checkable arithmetic; a model that could
change a name or a number would end that, so the guard matters more than the
feature.

Nothing here requires Ollama to be running. The tests that would need it check
the guard directly instead, which is the part that has to be right.
"""

from storyatlas_engine import polish


def test_the_engine_does_not_call_a_model_unless_asked():
    result = polish.smooth("Aldric Vane died in 1147.")
    assert result.text == "Aldric Vane died in 1147."
    assert not result.accepted
    assert "disabled" in result.reason


def test_facts_are_numbers_and_names():
    facts = polish.facts_in("Aldric Vane died at Dawnhold in 1147.")
    assert "1147" in facts["numbers"]
    assert "Aldric" in facts["names"]


def test_a_leading_capital_is_not_mistaken_for_a_name():
    """Otherwise reordering a clause looks like a name appearing or vanishing,
    and every honest rewrite gets rejected."""
    assert "The" not in polish.facts_in("The siege ended.")["names"]


def test_the_guard_notices_a_changed_year():
    before = polish.facts_in("Aldric died in 1147.")
    after = polish.facts_in("Aldric died in 1174.")
    assert before["numbers"] != after["numbers"]


def test_the_guard_notices_a_changed_name():
    before = polish.facts_in("Aldric died at Dawnhold.")
    after = polish.facts_in("Aldric died at Emberfall.")
    assert before["names"] != after["names"]


def test_the_guard_allows_a_pure_rewording():
    before = polish.facts_in("In 1147, Aldric died at Dawnhold.")
    after = polish.facts_in("Aldric died at Dawnhold in 1147.")
    assert before == after


def test_an_unreachable_model_returns_the_original_untouched():
    """Every failure path gives back the sentence that went in. There is no
    path where a caller silently receives altered facts, and none where this
    raises."""
    sentence = "Aldric Vane died in 1147."
    result = polish.smooth(sentence, enabled=True,
                           endpoint="http://127.0.0.1:1", timeout=0.2)
    assert result.text == sentence
    assert not result.accepted
    assert "no local model reachable" in result.reason


def test_probing_an_absent_model_is_false_not_an_exception():
    assert polish.available(endpoint="http://127.0.0.1:1", timeout=0.2) is False
    assert polish.models(endpoint="http://127.0.0.1:1", timeout=0.2) == []


def test_an_empty_sentence_is_left_alone():
    assert polish.smooth("   ", enabled=True).text == "   "


def test_the_report_says_so_when_nothing_is_running():
    """Pointed at a dead endpoint so the suite never waits on a live service —
    a test whose result depends on what happens to be installed is not a test."""
    text = polish.report(endpoint="http://127.0.0.1:1", timeout=0.2)
    assert "not reachable" in text
    assert "Nothing in the engine needs it" in text
