"""Phase 3 — the analyzer.

`analyze_image(path) -> SceneAnalysis` sends one photo to a vision model and asks it to
describe WHY the image looks the way it does — the lighting, the atmosphere, the materials,
any existing grade — as one structured JSON object. This block is *descriptive only*; it
contains no edits (see look-schema-v0.1.md section 3). The planner (Phase 4) is the module
that decides what to change; this module only observes.

Model choice: `google/gemini-2.5-flash`, chosen by a real, ground-truth comparison (see
DECISIONS.md D2.9) — a photo with a deliberately shifted face hue, run through six candidate
models. Three caught it correctly; this was the cheapest of those three. The model id is a
parameter, not baked in, per src/vlm_client's design.
"""

from __future__ import annotations

import hashlib
import json
import os

from pydantic import ValidationError

from src.schema.models import SceneAnalysis
from src.vlm_client import ask_the_model

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_DIR = os.path.join(ROOT, "runs", "cache")

DEFAULT_MODEL = "google/gemini-2.5-flash"

SCHEMA_JSON = json.dumps(SceneAnalysis.model_json_schema())

PROMPT = f"""You are analyzing a photograph for a cinematic color-grading tool. Describe WHY \
the image looks the way it does — do not suggest any edits.

Return ONLY a single JSON object matching this exact JSON Schema (no markdown fences, no \
commentary before or after):

{SCHEMA_JSON}

Requirements:
- lighting: identify the primary light source, its direction, quality (hard/soft/diffused), \
and estimate the color temperature in Kelvin.
- existing_grade: say whether the image already looks color-graded (vs. a flat/unprocessed \
photo), and list the visible characteristics if so.
- mood_tags: 3-6 words describing the emotional tone.
- material_map_notes: this is critical. Identify any ENVIRONMENTAL color source that is a \
property of a MATERIAL or SURFACE, not of the light itself — tinted glass, neon signage, a \
painted wall, a colored screen or practical lamp, colored fabric reflecting onto skin. For each \
one, name the region, the material, its approximate hue in degrees, and set "warning" to a \
non-empty explanation. This list must not be confused with lighting.secondary_sources (which is \
for actual light sources, e.g. a practical lamp's own light, not a surface reflecting color). \
If there is truly no such material in the frame, return an empty list — do not invent one.
"""


def _image_hash(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _cache_path(image_hash: str, model: str) -> str:
    # The model is part of the cache key: different models can disagree, and a cached
    # Gemini answer should never be silently served for a Claude request.
    safe_model = model.replace("/", "_")
    return os.path.join(CACHE_DIR, f"{image_hash}__{safe_model}.json")


def _extract_json(text: str) -> dict:
    """Models sometimes wrap JSON in ```json fences despite instructions not to. Strip them."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.rstrip().endswith("```"):
            text = text.rstrip()[: -3]
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    return json.loads(text.strip())


def analyze_image(path: str, model: str = DEFAULT_MODEL, use_cache: bool = True) -> SceneAnalysis:
    """Analyze one image, returning a validated SceneAnalysis.

    Results are cached by (image content hash, model) in runs/cache/, since analysis calls
    cost real money and the same sample images get analyzed repeatedly during development.
    """
    image_hash = _image_hash(path)
    cache_file = _cache_path(image_hash, model)

    if use_cache and os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as fh:
            return SceneAnalysis.model_validate(json.load(fh))

    reply = ask_the_model(path, PROMPT, model=model, max_tokens=2048)
    scene = _parse_or_repair(reply, path, model)

    if use_cache:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as fh:
            json.dump(scene.model_dump(mode="json"), fh, indent=2)

    return scene


def _parse_or_repair(reply: str, path: str, model: str) -> SceneAnalysis:
    """Parse the model's reply as SceneAnalysis; on failure, send the error back for one retry."""
    try:
        return SceneAnalysis.model_validate(_extract_json(reply))
    except (json.JSONDecodeError, ValidationError) as first_error:
        repair_prompt = (
            f"{PROMPT}\n\nYour previous reply failed to parse as valid JSON matching the "
            f"schema. The error was:\n{first_error}\n\nYour previous reply was:\n{reply}\n\n"
            "Reply again with ONLY the corrected JSON object."
        )
        retry_reply = ask_the_model(path, repair_prompt, model=model, max_tokens=2048)
        try:
            return SceneAnalysis.model_validate(_extract_json(retry_reply))
        except (json.JSONDecodeError, ValidationError) as second_error:
            raise ValueError(
                f"analyzer could not get valid SceneAnalysis JSON after one repair attempt.\n"
                f"First error: {first_error}\nSecond error: {second_error}\n"
                f"Final raw reply: {retry_reply}"
            ) from second_error
