from contextcore_engine.confidence import assess_confidence


def test_no_hits_is_none_level():
    result = assess_confidence([])
    assert result == {"level": "none", "top_score": 0.0, "gap": 0.0}


def test_strong_single_hit_is_high_confidence():
    result = assess_confidence([(0, 0.9), (1, 0.1)])
    assert result["level"] == "high"


def test_close_scores_are_lower_confidence_than_a_clear_gap():
    close = assess_confidence([(0, 0.4), (1, 0.38)])
    clear = assess_confidence([(0, 0.4), (1, 0.1)])
    assert close["level"] != "high"
    assert clear["level"] == "high"


def test_weak_top_score_is_low_confidence():
    result = assess_confidence([(0, 0.05)])
    assert result["level"] == "low"
