"""ValidWindow is the piece the whole canon story rests on, so it gets tested
on its own before anything composes it."""

import pytest

from creativeos_engine.graph import ValidWindow


def test_unbounded_window_contains_everything():
    always = ValidWindow()
    assert always.contains(-9999)
    assert always.contains(0)
    assert always.contains(9999)


def test_half_open_interval_excludes_its_end():
    window = ValidWindow(100, 200)
    assert window.contains(100)
    assert window.contains(199)
    assert not window.contains(200)
    assert not window.contains(99)


def test_open_ended_windows():
    assert ValidWindow(start=100).contains(10_000)
    assert not ValidWindow(start=100).contains(99)
    assert ValidWindow(end=100).contains(-10_000)
    assert not ValidWindow(end=100).contains(100)


def test_adjacent_windows_do_not_overlap():
    """'Alive until 300' then 'dead from 300' is continuity, not a conflict.
    If this ever returns True, every character death becomes a false positive."""
    assert not ValidWindow(0, 300).overlaps(ValidWindow(300, 600))
    assert not ValidWindow(300, 600).overlaps(ValidWindow(0, 300))


def test_genuinely_overlapping_windows_are_detected():
    assert ValidWindow(0, 400).overlaps(ValidWindow(300, 600))
    assert ValidWindow(300, 600).overlaps(ValidWindow(0, 400))
    assert ValidWindow(100, 200).overlaps(ValidWindow(120, 180))  # fully contained


def test_unbounded_windows_overlap_everything():
    assert ValidWindow().overlaps(ValidWindow(300, 600))
    assert ValidWindow(300, 600).overlaps(ValidWindow())
    assert ValidWindow(start=500).overlaps(ValidWindow(end=501))
    assert not ValidWindow(start=500).overlaps(ValidWindow(end=500))


def test_backwards_window_is_rejected():
    with pytest.raises(ValueError):
        ValidWindow(300, 100)
    with pytest.raises(ValueError):
        ValidWindow(100, 100)  # empty half-open interval is meaningless


def test_describe_is_human_readable():
    assert ValidWindow().describe() == "always"
    assert ValidWindow(100, 200).describe() == "100–200"
    assert ValidWindow(start=100).describe() == "from 100"
    assert ValidWindow(end=200).describe() == "until 200"
