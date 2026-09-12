"""Phase 8 — grouping the cast inside the timeline.

*"He's grouping the timelines well, but he does not group characters when they
appear within the timeline."*
"""

import pytest

from storyatlas_engine import grouping, read

SAGA = """CHAPTER ONE

Aldric Vane was born in the year 1100. Mara Sadel was born in the year 1105.

***

In the year 1140, Aldric Vane was crowned at Dawnhold. Mara Sadel watched.

***

Mara Sadel died in the year 1150. Aldric Vane died in the year 1160.

***

CHAPTER TWO

Kesh Oru was born in the year 1200. In the year 1230, Kesh Oru was crowned
at Emberfall.
"""


@pytest.fixture
def saga():
    return read(SAGA)


def test_eras_carry_a_cast_not_just_events(saga):
    eras = grouping.eras(saga)
    assert eras
    assert any(era.alive for era in eras)


def test_alive_is_computed_and_appearing_is_counted(saga):
    """The two are different numbers, and the gap between them is the point."""
    era = next(e for e in grouping.eras(saga) if e.start == 1120)
    assert set(era.alive) == {"Aldric Vane", "Mara Sadel"}
    assert era.appears == []
    assert era.offstage == ["Aldric Vane", "Mara Sadel"]


def test_the_dead_are_not_counted_alive(saga):
    era = next(e for e in grouping.eras(saga) if e.start == 1230)
    assert "Aldric Vane" not in era.alive
    assert "Kesh Oru" in era.alive


def test_births_and_deaths_land_in_their_own_era(saga):
    eras = {e.start: e for e in grouping.eras(saga)}
    assert "Aldric Vane" in eras[1100].born
    assert "Mara Sadel" in eras[1150].died


def test_era_boundaries_do_not_move_when_the_draft_grows():
    """Buckets align to multiples of the span, so the same era means the same
    years however the draft changes. A timeline whose boundaries shift when you
    add a sentence is one nobody can navigate twice."""
    first = grouping.eras(read("Aldric Vane was born in the year 1104."))
    second = grouping.eras(read(
        "Aldric Vane was born in the year 1104. Mara Sadel died in the year 1099."))
    assert first[0].start % 10 == 0
    assert all(era.start % 10 == 0 for era in second)


def test_cast_at_answers_who_can_be_in_this_room(saga):
    assert grouping.cast_at(saga, 1145) == ["Aldric Vane", "Mara Sadel"]
    assert grouping.cast_at(saga, 1205) == ["Kesh Oru"]


def test_generations_band_by_birth_not_by_slice(saga):
    bands = dict(grouping.generations(saga, span=100))
    assert set(bands[1100]) == {"Aldric Vane", "Mara Sadel"}
    assert bands[1200] == ["Kesh Oru"]


def test_co_presence_pairs_are_counted_once(saga):
    """An unordered pair counted twice doubles every edge weight in the mind
    map and silently changes which characters look central."""
    pairs = grouping.co_presence(saga)
    for first, second in pairs:
        assert first < second
        assert (second, first) not in pairs


def test_circles_group_characters_who_share_scenes(saga):
    circles = grouping.circles(saga)
    biggest = circles[0]
    assert "Aldric Vane" in biggest.members and "Mara Sadel" in biggest.members
    assert "Kesh Oru" not in biggest.members


def test_a_character_who_shares_nothing_is_their_own_circle(saga):
    solo = [c for c in grouping.circles(saga) if c.members == ["Kesh Oru"]]
    assert solo


def test_raising_the_threshold_breaks_weak_links(saga):
    loose = grouping.circles(saga, minimum=1)
    strict = grouping.circles(saga, minimum=99)
    assert len(strict) >= len(loose)
    assert all(c.size == 1 for c in strict)


def test_the_grid_has_a_row_per_character_and_a_column_per_era(saga):
    grid = grouping.timeline_grid(saga)
    assert grid["rows"]
    assert all(len(row["cells"]) == len(grid["eras"]) for row in grid["rows"])


def test_the_grid_distinguishes_present_from_merely_alive(saga):
    grid = grouping.timeline_grid(saga)
    aldric = next(r for r in grid["rows"] if r["name"] == "Aldric Vane")
    assert "here" in aldric["cells"]
    assert "alive" in aldric["cells"]
    assert "gone" in aldric["cells"]


def test_the_grid_renders_without_a_character(saga):
    assert "no dated characters" in grouping.render_grid(
        grouping.timeline_grid(read("")))


def test_grouping_is_deterministic(saga):
    assert grouping.render_grid(grouping.timeline_grid(saga)) == \
           grouping.render_grid(grouping.timeline_grid(read(SAGA)))


def test_an_empty_draft_produces_no_eras():
    assert grouping.eras(read("")) == []
