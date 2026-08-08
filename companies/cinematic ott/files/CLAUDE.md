# CLAUDE.md — Project Constitution (read me first, every session)

## What this project is

An AI cinematic grading engine. A user gives a REFERENCE image (a screenshot with a look
they love) and a TARGET image (their own photo). The system reconstructs WHY the reference
looks the way it does (lighting, atmosphere, materials, camera behavior) and applies those
CAUSES to the target — never blindly copying colors.

This is NOT a filter app, NOT a LUT app, NOT color transfer. It is Scene Reconstruction.

## Non-negotiable laws (never violate, never "simplify away")

1. **Parametric only.** The system outputs edit PARAMETERS (white balance, curves, HSL,
   split tone) applied through masks. It NEVER generates or resynthesizes pixels. No
   diffusion models, no inpainting, no generative fill. Ever.
2. **Every operation needs a justification.** Any edit operation without a `cause_ref`
   linking it to a declared photographic cause is rejected by the validator.
3. **Faces are sacred.** Protections in the schema are hard clamps enforced by the
   executor AFTER the AI's plan, no matter what the plan says. Skin hue shift max 8°,
   no texture/clarity ops on faces, eyes never hue-shifted.
4. **The blue-glass law.** Environmental/material color in the reference (e.g., blue
   tinted glass behind the subject) must NEVER transfer onto target skin or unrelated
   regions. The analyzer must flag material colors; the planner must declare them in
   `do_not_transfer`. This is permanent eval case #001.
5. **Local over global.** Global operations are allowed only with explicit justification
   (e.g., atmospheric haze affects everything). Unjustified global ops are rejected.
6. **Critic before accept.** No output ships without passing the critic rubric or
   exhausting max 3 iterations (then return best attempt WITH warnings).

## Architecture (6 modules, keep them separate)

```
src/
  schema/      # Pydantic models of the Look Schema v0.1 + validator  (Phase 1)
  segment/     # Semantic masks: person, face, skin, sky, etc.        (Phase 2)
  analyze/     # VLM call -> scene_analysis JSON for any image        (Phase 3)
  plan/        # VLM call -> intent + operations (validated)          (Phase 4)
  execute/     # Applies operations through masks. Pure Python/OpenCV (Phase 5)
  critic/      # VLM call -> rubric scores; drives iteration loop     (Phase 6)
evalset/       # Reference/target pairs + expected behaviors          (Phase 7)
cli.py         # grade --ref ref.jpg --target me.jpg -> output + log
```

Modules communicate ONLY through the Look Schema JSON. The analyzer never touches
pixels. The executor never calls an AI. This separation is the product's moat.

## Tech stack (do not add frameworks without asking the user)

- Python 3.11+, `uv` or `pip` for deps
- Pydantic v2 (schema + validation)
- OpenCV + NumPy + Pillow (executor)
- `ultralytics` YOLOv8-seg (person/objects, CPU is fine) + `mediapipe` (face/skin regions)
- **OpenRouter** (OpenAI-compatible API) for analyzer/planner/critic vision calls, via the
  single shared function `src/vlm_client.ask_the_model(image_path, prompt, model)`. The model
  id is a **configurable string, not hardcoded** — different phases (or future tiers) may use
  different models; pick per-call based on `scripts/test_vision_models.py` comparisons.
- API key from environment variable OPENROUTER_API_KEY (a `.env` file, never committed)
- No web framework until Phase 8. CLI first.

## Working style for Claude Code

- Execute ONE phase at a time from BUILD_PLAN.md. After each phase: run its acceptance
  test, show the user the result in plain language, then stop and wait.
- Write tests next to each module (`test_*.py`, runnable with pytest).
- Log everything: every operation applied, every justification, every clamp event,
  every critic score — to `runs/<timestamp>/log.json`. The log is a product feature.
- The user does not code. Explain what you did after each phase in simple words,
  2–4 sentences, no jargon. If something fails, say what failed and what you'll try.
- Never mark a phase done if its acceptance test fails.
- Commit to git after every completed phase with a clear message.

## Reference documents in this folder

- `look-schema-v0.1.md` — the full schema spec. Implement it faithfully in Phase 1.
- `BUILD_PLAN.md` — the phase-by-phase build order with acceptance criteria.
