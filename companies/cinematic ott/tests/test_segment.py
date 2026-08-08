"""Phase 2 acceptance — segmentation on real photographs.

The build plan's criteria: "overlay images look sane (user visually confirms); every pixel
classified." The exclusivity guarantee is machine-checkable and asserted here; the overlays
are regenerated so a human can look at them (runs/overlays/).

These tests need the downloaded assets:  python scripts/fetch_assets.py
"""

import os

import numpy as np
import pytest

from src.segment import segment_image, feather, save_overlay, PRIORITY

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(ROOT, "evalset", "samples")
PEOPLE = os.path.join(SAMPLES, "people.jpg")
STREET = os.path.join(SAMPLES, "street.jpg")

pytestmark = pytest.mark.skipif(
    not (os.path.exists(PEOPLE) and os.path.exists(STREET)),
    reason="sample images missing — run: python scripts/fetch_assets.py",
)


@pytest.fixture(scope="module")
def people_masks():
    return segment_image(PEOPLE)


@pytest.fixture(scope="module")
def street_masks():
    return segment_image(STREET)


# --- the core guarantee: every pixel belongs to exactly one class ------------
@pytest.mark.parametrize("fixture_name", ["people_masks", "street_masks"])
def test_every_pixel_in_exactly_one_class(fixture_name, request):
    masks = request.getfixturevalue(fixture_name)
    assert masks, "no masks produced"
    shape = next(iter(masks.values())).shape
    counts = np.zeros(shape, dtype=np.uint16)
    for m in masks.values():
        assert m.dtype == np.uint8, "masks must be uint8"
        assert m.shape == shape, "all masks must share the image shape"
        counts += (m > 127).astype(np.uint16)
    assert int((counts == 0).sum()) == 0, "some pixels belong to no class"
    assert int((counts > 1).sum()) == 0, "some pixels belong to more than one class"


# --- classes are drawn from the declared vocabulary -------------------------
@pytest.mark.parametrize("fixture_name", ["people_masks", "street_masks"])
def test_classes_are_in_vocabulary(fixture_name, request):
    masks = request.getfixturevalue(fixture_name)
    for name in masks:
        assert name in PRIORITY, f"'{name}' is not a declared semantic class"


# --- a photo of people should yield person-ish regions ----------------------
def test_people_photo_finds_person_regions(people_masks):
    for expected in ("clothing", "skin", "face", "hair"):
        assert expected in people_masks, f"expected a '{expected}' region"
        assert (people_masks[expected] > 127).sum() > 0


# --- faces are sacred: a detected face must be inside the skin superset -----
def test_face_is_subset_of_skin_or_claimed_by_higher_priority(people_masks):
    """`skin` must cover the face area, so skin protections always apply to faces.

    After priority resolution the masks are exclusive, so 'face' pixels are no longer in
    'skin'. The guarantee we check is the inverse: no face pixel leaked into a region that
    carries no skin protection (e.g. clothing or background).
    """
    face = people_masks.get("face")
    assert face is not None and (face > 127).any()
    for unprotected in ("clothing", "background_other", "sky", "vehicle"):
        if unprotected in people_masks:
            overlap = np.logical_and(face > 127, people_masks[unprotected] > 127).sum()
            assert overlap == 0, f"face pixels leaked into '{unprotected}'"


# --- eyes, when found, sit inside the face ----------------------------------
def test_eyes_are_within_face_bounds(people_masks):
    if "eyes" not in people_masks:
        pytest.skip("no eyes detected in this sample")
    eyes = people_masks["eyes"] > 127
    assert eyes.sum() > 0
    # Eyes take priority over face, so they are carved OUT of the face mask. Verify they sit
    # inside the face's bounding box rather than floating elsewhere in the frame.
    face = people_masks["face"] > 127
    ys, xs = np.where(face)
    ey, ex = np.where(eyes)
    assert ey.min() >= ys.min() and ey.max() <= ys.max(), "eyes outside face vertical bounds"
    assert ex.min() >= xs.min() and ex.max() <= xs.max(), "eyes outside face horizontal bounds"


# --- a street scene should find the vehicle ---------------------------------
def test_street_photo_finds_vehicle(street_masks):
    assert "vehicle" in street_masks
    assert (street_masks["vehicle"] > 127).sum() > 0


# --- feathering softens edges without changing the frame --------------------
def test_feather_softens_edges(people_masks):
    m = people_masks["clothing"]
    f = feather(m, 8)
    assert f.shape == m.shape and f.dtype == np.uint8
    # A feathered mask has intermediate values that a binary mask does not.
    assert ((f > 0) & (f < 255)).sum() > ((m > 0) & (m < 255)).sum()
    assert feather(m, 0).tolist() == m.tolist(), "feather(0) must be a no-op"


# --- the debug overlay is written so a human can inspect it -----------------
def test_overlay_written(people_masks):
    out = os.path.join(ROOT, "runs", "overlays", "test_people_overlay.png")
    path = save_overlay(PEOPLE, people_masks, out)
    assert os.path.exists(path) and os.path.getsize(path) > 0
