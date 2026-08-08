"""Phase 3 — scenes: where they start, who is in them, where and when.

The Story Atlas app has a scene database the writer fills in by hand.
Everything needed to fill it is already in the prose.
"""

from storyatlas_engine import read

DRAFT = """CHAPTER ONE

Chancellor Aldric Vane waited at Ash Harbour. Mara Sadel stood beside him.

***

Three years later, Mara Sadel married Tobin Reyes at Dawnhold.
"""


def test_a_draft_splits_into_scenes():
    assert len(read(DRAFT).scenes) == 2


def test_a_marker_heads_the_scene_it_introduces():
    """Regression: a marker on its own line used to become a phantom empty
    scene before every real one."""
    scenes = read(DRAFT).scenes
    assert scenes[0].marker == "CHAPTER ONE"
    assert scenes[0].present            # it has the prose, not nothing
    assert all(s.text.strip() for s in scenes)


def test_a_scene_knows_who_is_present():
    scene = read(DRAFT).scenes[0]
    assert "Chancellor Aldric Vane" in scene.present
    assert "Mara Sadel" in scene.present


def test_a_scene_knows_when_it_happens():
    scene = read(DRAFT).scenes[1]
    assert scene.time is not None
    assert scene.time.kind == "offset"


def test_a_scene_carries_its_events():
    scenes = read(DRAFT).scenes
    assert any(scene.events for scene in scenes)


def test_a_slugline_gives_the_place():
    r = read("INT. THE BRIDGE — NIGHT\n\nAldric Vane checked the charts.")
    assert r.scenes[0].place == "The Bridge"


def test_a_place_carries_forward_until_the_text_names_a_new_one():
    """Prose states a location once and assumes it for several scenes."""
    r = read(
        "INT. THE BRIDGE — NIGHT\n\nAldric Vane checked the charts.\n\n"
        "***\n\nAldric Vane waited.\n"
    )
    assert r.scenes[1].place == "The Bridge"


def test_blank_lines_alone_split_scenes():
    r = read("Aldric Vane waited.\n\nMara Sadel arrived.\n")
    assert len(r.scenes) == 2


def test_scenes_can_be_found_for_a_character():
    r = read(DRAFT)
    assert len(r.scenes_with("Mara Sadel")) == 2
    assert len(r.scenes_with("Chancellor Aldric Vane")) == 1


def test_a_character_present_throughout_is_identified():
    r = read(DRAFT)
    assert r.who_is_in_every_scene() == ["Mara Sadel"]


def test_a_scene_has_a_usable_title():
    for scene in read(DRAFT).scenes:
        assert scene.title.strip()


def test_scene_detection_is_deterministic():
    first = [s.describe() for s in read(DRAFT).scenes]
    second = [s.describe() for s in read(DRAFT).scenes]
    assert first == second
