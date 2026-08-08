# BUILD_PLAN.md — Execute phases in order. One phase per session is fine.

Rule: a phase is DONE only when its acceptance test passes. Then explain the result to
the user in plain language and stop.

---

## Phase 0 — Environment & skeleton

Tasks:
1. Create the folder structure from CLAUDE.md. Init git. Create `.gitignore`
   (include `.env`, `runs/`, model weights, `__pycache__`).
2. Create `pyproject.toml` or `requirements.txt` with: pydantic, opencv-python,
   numpy, pillow, ultralytics, mediapipe, openai (OpenRouter uses the OpenAI-compatible
   client), python-dotenv, pytest, rich.
3. Install dependencies. Download YOLOv8-seg small weights (`yolov8s-seg.pt`).
4. Create `.env.example` with `OPENROUTER_API_KEY=your_key_here`. Tell the user:
   get a key at openrouter.ai → Keys, put it in a file named `.env`.
5. Smoke test script `scripts/smoke.py`: load an image with OpenCV, run YOLO on it,
   make one tiny OpenRouter vision API call via `src/vlm_client.py`, print "ALL SYSTEMS OK".

Acceptance: `python scripts/smoke.py` prints ALL SYSTEMS OK.

---

## Phase 1 — Schema + validator (`src/schema/`)

Tasks:
1. Implement Look Schema v0.1 from `look-schema-v0.1.md` as Pydantic models:
   Scene analysis, Intent, Operation, Adjustments, Protections, CoherenceRules,
   CriticConfig, ExportConfig, and the top-level `Look`.
2. Implement `validate_look(look) -> ValidationReport` with the 6 validation rules
   from section 10 of the spec:
   - every op's cause_ref must exist in intent.transfer
   - every material_map warning must have a matching do_not_transfer entry
   - global ops require justification
   - unknown fields ignored with warning; unknown major version rejected
3. Implement `default_protections()` returning the hard clamp values from the spec.
4. Write `tests/test_schema.py`: a valid look passes; a look with an unjustified op
   fails; a look with a material warning but no do_not_transfer fails.

Acceptance: `pytest tests/test_schema.py` green.

---

## Phase 2 — Segmentation (`src/segment/`)

Tasks:
1. `segment_image(path) -> dict[semantic_class, mask]` where masks are uint8 arrays.
   - YOLOv8-seg for: person, sky-adjacent classes, vehicle, etc. Map COCO classes to
     our semantic_class vocabulary (person → subject; use heuristics for sky: top
     region + color/gradient check is acceptable for v0).
   - MediaPipe face mesh / selfie segmentation for: face, skin (face skin at minimum),
     eyes, hair (approximate hair via selfie-seg minus face is acceptable for v0).
   - `background_other` = everything not otherwise claimed. Every pixel belongs to
     exactly one class (resolve overlaps by priority: eyes > face > skin > hair >
     clothing > subject > named classes > background_other).
2. Feathering utility: `feather(mask, px)` via Gaussian blur.
3. Debug output: save a color-coded overlay PNG so the user can SEE the masks.
4. `tests/test_segment.py` on 2 sample images placed in `evalset/samples/`.

Acceptance: overlay images look sane (user visually confirms); every pixel classified.

---

## Phase 3 — Analyzer (`src/analyze/`)

Tasks:
1. `analyze_image(path, masks) -> SceneAnalysis` using one vision call through the shared
   `src/vlm_client.ask_the_model()` (OpenRouter; model id configurable, chosen from the
   `scripts/test_vision_models.py` comparison — not hardcoded to one provider/model).
   The prompt must instruct the model to return ONLY JSON matching the SceneAnalysis
   schema (send the JSON schema in the prompt). Parse with Pydantic; on parse failure,
   retry once with the error message included.
2. The prompt MUST require: lighting source/direction/quality/temp estimate, existing
   grade detection, mood tags, and `material_map_notes` with explicit warnings for
   environmental color sources (glass, neon, painted walls, colored practicals).
3. Cache results by image hash in `runs/cache/` (analysis calls cost money).
4. `tests/test_analyze.py`: run on the sample images, assert valid SceneAnalysis.

Acceptance: analyzer returns valid, sensible SceneAnalysis for both samples; the user
reads the plain-language summary and confirms it matches what they see in the photos.

---

## Phase 4 — Planner (`src/plan/`)

Tasks:
1. `make_plan(ref_analysis, target_analysis, target_masks) -> Look` via one
   `src/vlm_client.ask_the_model()` call. Prompt includes: both analyses, available semantic classes present in the
   target, the operations vocabulary, and the validation rules. Model returns intent
   + operations JSON.
2. Run `validate_look` on the result. If invalid, send the validation errors back to
   the model for ONE repair attempt. Still invalid → fail loudly with the report.
3. Every operation's `justification.statement` must be human-readable — these become
   the user-facing "why" log.
4. `tests/test_plan.py`: with a mocked ref analysis containing a blue-glass material
   warning, assert the produced Look contains a matching do_not_transfer entry and no
   blue hue shift op targeting skin.

Acceptance: pytest green, including the blue-glass planner test.

---

## Phase 5 — Executor (`src/execute/`)

Pure image math. No AI calls in this module.

Tasks:
1. `apply_look(image, masks, look) -> (edited_image, ExecutionLog)`.
2. Implement adjustments (operate in float32, 0–1 range):
   - White balance: mired shift → per-channel gains (approximate: warm = +R/−B).
     Keep it simple and monotonic; document the approximation.
   - Exposure: multiply by 2^ev.
   - Tone curve: pivot contrast (smooth S-curve around pivot), black_lift as additive
     floor with rolloff, highlight_rolloff as soft-knee compression above 0.8.
   - HSL bands: convert to HSV, apply hue_shift/sat_scale/lum_shift inside the band
     with smooth falloff at band edges.
   - Split tone: add hue tint scaled by (1−L) for shadows, by L for highlights.
   - Saturation scale.
3. Apply per region through feathered masks: `out = mask*edited + (1−mask)*out`.
4. Enforce protections AFTER computing each op: clamp values, record every clamp event
   in the ExecutionLog.
5. Determinism test: same inputs → byte-identical output.
6. Visual test script: apply a hand-written obvious Look (e.g., strong warm skin,
   cool background) to a sample and save before/after for the user to inspect.

Acceptance: determinism test green; user visually confirms the obvious-Look demo does
what it says (warm skin, cool background, face intact).

---

## Phase 6 — Critic + iteration loop (`src/critic/`)

Tasks:
1. `critique(ref_path, target_path, output_path) -> CriticScores` — one
   `src/vlm_client.ask_the_model()` vision call with all three images, scoring the 6 rubric dimensions (0–1 each),
   returning JSON. Include ExecutionLog clamp count in the prompt (many clamps →
   the plan was fighting the protections → note it).
2. Loop in `src/pipeline.py`:
   segment → analyze(ref) → analyze(target) → plan → execute → critique →
   if fail and iterations < 3: send critic feedback to planner for a revised Look →
   repeat. Return best attempt + full log.
3. `cli.py`: `python cli.py --ref evalset/samples/ref1.jpg --target evalset/samples/t1.jpg`
   → writes `runs/<ts>/output.jpg`, `look.json`, `log.json`, and prints a plain-language
   summary: what it saw, what it decided, what it changed, scores.

Acceptance: full pipeline runs end-to-end on a sample pair without errors; log contains
justifications for every applied op.

---

## Phase 7 — Eval harness (`evalset/`)

Tasks:
1. Folder format: `evalset/cases/<case_id>/ref.jpg, target.jpg, expectations.md`.
2. Case 001 is the blue-glass law (ask the user to supply or approve found images:
   ref = subject with blue glass background; target = people outdoors in red).
   Expectation: skin hue shift ≤ protections, no blue cast on clothing/skin,
   do_not_transfer entry present.
3. `scripts/run_evals.py`: runs the pipeline on every case, checks machine-checkable
   expectations (parse look.json + measure region hue deltas), prints a pass/fail
   table, saves all outputs for visual review.
4. Ask the user to collect 10–20 more pairs over time; add each interesting failure
   as a new numbered case. THE EVAL SET ONLY GROWS. Never delete a case.

Acceptance: eval runner produces the table; case 001 passes.

---

## Phase 8 (later, only when 001–010 pass) — Minimal web UI

Flask or FastAPI single page: upload ref + target, show before/after slider, show the
"why" log in plain language, download output + look.json. No accounts, no payments yet.

---

## Cost & expectation notes (tell the user)

- Analyzer + planner + critic ≈ 3–7 vision calls per grade ≈ a few cents per image.
- v0 output will NOT look world-class immediately. The product is the LOOP:
  run evals → find ugly results → improve prompts/executor → evals grow → quality climbs.
  Weeks of iteration, not one magic build.
