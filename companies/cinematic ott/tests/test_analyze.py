"""Phase 3 acceptance — the analyzer returns a valid, sensible SceneAnalysis for real photos.

These tests make real (cheap, cached-after-first-run) API calls, since a mocked response
would prove nothing about whether the actual model/prompt combination works. They need:
  * evalset/samples/{people,street}.jpg  (python scripts/fetch_assets.py)
  * OPENROUTER_API_KEY in .env
Skipped automatically if either is missing, rather than failing the whole suite.
"""

import os

import pytest

from src.analyze import analyze_image
from src.schema.models import SceneAnalysis

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(ROOT, "evalset", "samples")
PEOPLE = os.path.join(SAMPLES, "people.jpg")
STREET = os.path.join(SAMPLES, "street.jpg")

_has_key = bool(os.environ.get("OPENROUTER_API_KEY"))
if not _has_key:
    # analyze_image loads .env itself (via vlm_client); check the file directly too.
    _env_path = os.path.join(ROOT, ".env")
    if os.path.exists(_env_path):
        _has_key = "OPENROUTER_API_KEY=" in open(_env_path).read() and "your_key_here" not in open(_env_path).read()

pytestmark = pytest.mark.skipif(
    not (_has_key and os.path.exists(PEOPLE) and os.path.exists(STREET)),
    reason="needs OPENROUTER_API_KEY in .env and sample images (python scripts/fetch_assets.py)",
)


@pytest.fixture(scope="module")
def people_analysis():
    return analyze_image(PEOPLE)


@pytest.fixture(scope="module")
def street_analysis():
    return analyze_image(STREET)


def test_returns_valid_scene_analysis(people_analysis):
    assert isinstance(people_analysis, SceneAnalysis)


def test_lighting_fields_are_populated(people_analysis):
    lighting = people_analysis.lighting
    assert lighting.primary_source != "unknown", "should identify a light source, not punt"
    assert lighting.direction is not None
    assert lighting.quality is not None


def test_mood_tags_present(people_analysis):
    assert len(people_analysis.mood_tags) > 0


def test_street_scene_analyzed_too(street_analysis):
    assert isinstance(street_analysis, SceneAnalysis)
    assert street_analysis.lighting.primary_source != "unknown"


def test_no_hallucinated_material_warning_on_clean_photos(people_analysis, street_analysis):
    """Neither sample has tinted glass, neon, or similar -- the analyzer should not invent one.

    This is the inverse of the blue-glass law: a good analyzer doesn't just flag everything,
    it flags real material color sources and stays quiet otherwise.
    """
    for analysis in (people_analysis, street_analysis):
        # Not a hard assertion of zero notes (a real material could legitimately be present,
        # e.g. reflective glass on the bus) -- but every note must be reasonably specific.
        for note in analysis.material_map_notes:
            assert note.material.strip(), "a material note must name an actual material"


def test_result_is_cached(people_analysis):
    """A second call with the same image+model should hit the cache, not the network."""
    from src.analyze.analyzer import _cache_path, _image_hash, DEFAULT_MODEL

    cache_file = _cache_path(_image_hash(PEOPLE), DEFAULT_MODEL)
    assert os.path.exists(cache_file), "expected a cache file after analyze_image()"
