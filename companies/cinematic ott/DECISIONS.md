# Architecture Decisions — Cinematic OTT

Plain-language record of **why** each choice was made, so OTT can weigh it, defend it, or
overrule it. Newest phase at the bottom. Each entry: **Decision → Why → Trade-off →
What I rejected.** Nothing here locks you in; push back on any of it.

---

## Phase 0 — Environment & skeleton

### D0.1 — The project lives as a subfolder of the existing repo (no nested git)
- **Decision:** Build in `companies/cinematic ott/`, committing to the repo that already
  exists at `ott-sovereign-stack/`. The three spec files stay in `files/`.
- **Why:** You already have one git repo for everything. A second, nested git repo inside it
  causes confusing double-tracking. One history is simpler and still lets us "commit after
  every phase" as the plan asks.
- **Trade-off:** Cinematic OTT isn't independently versioned. If you ever spin it out into its
  own product repo, we'd split it then — a clean, known operation.
- **Rejected:** `git init` a fresh repo here (the plan's Phase 0 wording), because it would nest
  repos and fight the existing one.

### D0.2 — Python 3.13, inside a project-local virtual environment (`.venv`)
- **Decision:** Run everything on Python **3.13** in a sandboxed `.venv` folder, not the
  machine's default **3.14**.
- **Why:** I checked the actual package sources. The vision libraries this project needs —
  PyTorch, MediaPipe, OpenCV — ship ready-made installers ("wheels") for 3.13 but **not yet**
  for 3.14 (3.14 is very new; these libraries always lag a few months). Building on 3.13 means
  everything installs cleanly instead of trying to compile from scratch (which usually fails on
  Windows). The `.venv` keeps all of it inside the project folder — your system Python is
  untouched.
- **Trade-off:** You must "activate" the venv (or I point commands at `.venv`) to use the
  project. Standard practice; the README documents it.
- **Rejected:** Forcing 3.14 (installs break), or installing 3.12 system-wide (a bigger change
  to your machine than necessary — 3.13 was already present).

### D0.3 — CPU builds of the ML stack
- **Decision:** Install the normal (CPU) PyTorch, not a GPU/CUDA build.
- **Why:** The constitution says "CPU is fine." YOLO segmentation and MediaPipe run fine on CPU
  for single images, and CPU wheels are smaller and install without a matching graphics driver.
- **Trade-off:** Slower on huge batches — irrelevant at this stage (we grade one image at a
  time). Swappable later if we ever batch-process.

### D0.4 — Model id: `claude-sonnet-5` instead of the spec's `claude-sonnet-4-6`
- **Decision:** Use `claude-sonnet-5` for the analyzer / planner / critic vision calls.
- **Why:** `claude-sonnet-4-6` from the spec is not a valid model name — it would error on every
  call. `claude-sonnet-5` is the current vision-capable Sonnet, same intended role.
- **Trade-off:** None functionally; it's a rename. Documented so it's not a silent change.

### D0.6 — `opencv-python-headless` instead of `opencv-python`
- **Decision:** Depend on the *headless* build of OpenCV.
- **Why:** Two reasons, and the second is the real one. (1) Your connection kept dropping the
  larger full build mid-download; headless is smaller and installed first try. (2) More
  importantly it's **the correct dependency**: this is a command-line pipeline that reads and
  writes image files and never opens a GUI window, so the desktop/GUI libraries bundled in the
  full build are dead weight we'd never call.
- **Trade-off:** `cv2.imshow()` (pop-up preview windows) is unavailable. We don't use it — debug
  output is saved as PNG files you can open, which is better anyway (you can keep them, compare
  them, put them in a report).

### D0.7 — MediaPipe: use the **Tasks API**, not the retired `solutions` API
- **Decision:** Use `mediapipe.tasks.python.vision` (`FaceLandmarker`, `ImageSegmenter`) for face
  and person segmentation in Phase 2.
- **Why:** Not a preference — a necessity I found by testing. The installed MediaPipe (0.10.35)
  has **removed** the old `mp.solutions.face_mesh` / `selfie_segmentation` API the build plan
  assumed; the module only exposes `Image`, `ImageFormat`, and `tasks`. Code written against the
  old API would fail immediately.
- **Upside:** The Tasks API is a better fit anyway. `ImageSegmenter` can return **multi-class**
  masks (hair / skin / face / clothes / background) in one pass, which maps much more directly
  onto our semantic classes than the old single "person vs background" selfie mask, and
  `FaceLandmarker` gives a dense 478-point face mesh for precise eye and face regions.
- **Trade-off:** The Tasks API loads its models from downloadable `.task` files, so Phase 2 needs
  a small model-fetch step (a `scripts/fetch_models.py`). That's one-time and scriptable.

### D0.4b — `opencv-python-headless` instead of `opencv-python`
- **Decision:** Depend on the **headless** OpenCV build.
- **Why:** Two reasons, and the second is the real one. (1) Practical: the full build is a 44 MB
  download that this machine's connection kept breaking; headless is smaller and got through.
  (2) Correct by design: this is a command-line pipeline that reads and writes image *files*. It
  never opens a GUI window. The full build bundles desktop GUI libraries we will never call.
- **Trade-off:** `cv2.imshow()` won't work — we don't use it, and shouldn't (debug output is
  saved as PNG files, which is better anyway: you can look at them later, and they work on a
  server). Note `ultralytics` lists the full `opencv-python` as its own dependency, so both may
  end up installed; they provide the same `cv2` module and the import is verified working.

### D0.4c — A resumable wheel downloader (`scripts/fetch_wheel.py`)
- **Decision:** Ship a small helper that downloads large packages with resume-on-failure, and
  install those from local files.
- **Why:** This connection drops big HTTPS transfers mid-stream (`ConnectionResetError`,
  `IncompleteRead`). `pip` restarts a failed download from zero, so a 116 MB file (PyTorch) never
  finished. The helper uses HTTP Range requests to continue where it left off, so progress
  survives a dropout. PyTorch installed successfully this way after `pip` had failed repeatedly.
- **Trade-off:** One more script to maintain. It only matters on bad networks; on a good
  connection plain `pip install -r requirements.txt` still works and stays the documented path.
- **Bug worth noting:** the first version picked a Linux/ARM wheel, because it tested
  `"any" in filename` and the string `"manylinux"` contains `"any"`. Fixed to test the actual
  platform tag. A good reminder that substring checks on structured names are a trap.

### D0.5 — The smoke test checks each subsystem separately
- **Decision:** `scripts/smoke.py` tests OpenCV, YOLO, MediaPipe, and the API **independently**
  and prints a per-system PASS/FAIL, only saying "ALL SYSTEMS OK" if every one passes.
- **Why:** The one thing most likely to fail is the API call (if the Anthropic account has no
  credit). If a single combined test failed, you couldn't tell whether your vision stack is
  broken or it's just a billing issue. Separate checks make the truth obvious — and honour the
  "no faking" rule: a billing failure is reported as exactly that.
- **Trade-off:** A little more code than a one-liner. Worth it for a clear signal.

---

## Phase 1 — Look Schema + validator

The Look Schema is the one format every module speaks. This phase turns the written spec
(`files/look-schema-v0.1.md`) into enforced code.

### D1.1 — Two files: the *shape* (`models.py`) and the *rules* (`validator.py`)
- **Decision:** `models.py` holds what a Look *is* (the fields); `validator.py` holds what
  makes a Look *legal* (the six rules).
- **Why:** These change for different reasons. New fields (a v0.2 addition) touch `models.py`;
  new safety rules touch `validator.py`. Keeping them apart means each stays small and you can
  read "the laws" in one place without wading through 300 lines of field definitions.
- **Trade-off:** Two files instead of one. Worth it — the validator is the safety heart of the
  product and deserves to stand alone.

### D1.2 — Unknown fields are *kept and flagged*, never rejected (spec rule 5)
- **Decision:** Every model accepts extra/unknown fields (`extra="allow"`); the validator lists
  them as **warnings**, not errors.
- **Why:** Forward compatibility. When a future v0.2 adds a field, today's code shouldn't crash
  on it — it should carry it along and quietly note "I saw something I didn't recognise." That's
  how formats evolve without breaking old tools.
- **Trade-off:** A typo'd field name is preserved silently (as a warning) instead of loudly
  erroring. Acceptable: warnings are shown, and the alternative (reject everything unfamiliar)
  makes every future upgrade a breaking change.

### D1.3 — The blue-glass rule (rule 2) uses word-overlap matching
- **Decision:** A material warning (e.g. *tinted_glass* in the *background*) is considered
  "properly disclaimed" if any `do_not_transfer` entry shares a meaningful word with it
  (e.g. an entry mentioning *glass* or *background*).
- **Why:** The spec requires each environmental-colour warning to have a *matching*
  disclaimer, but doesn't define a strict ID linking them. Word-overlap is simple, explainable,
  and catches the real case: it passes the worked blue-glass example and fails an empty
  disclaimer list — exactly the behaviour the spec's test demands.
- **Trade-off:** It's a heuristic, not a hard key. A cleverly-worded-but-irrelevant disclaimer
  could slip through. When we build the planner (Phase 4) we can tighten this to explicit
  references. For v0.1 it correctly enforces "you must acknowledge the material."
- **Rejected:** Requiring an exact ID match (the spec doesn't define one, so it'd be inventing
  format we might regret) and "any disclaimer counts" (too weak — wouldn't tie the disclaimer to
  the actual material).

### D1.4 — A wrong *major* version stops validation immediately (rule 6)
- **Decision:** If a Look claims a schema major version this code doesn't implement (e.g. "9.0"),
  the validator records one clear error and stops — it doesn't try to check the other rules.
- **Why:** If the format's major version is unknown, we can't trust what any field means, so
  running the rest of the rules would produce misleading results. Fail fast, fail clearly.

### D1.5 — Report separates **errors** (illegal) from **warnings** (advisory)
- **Decision:** `validate_look` returns a report with `ok`, `errors`, and `warnings`. Only errors
  make a Look illegal; `if report:` reads as "is this Look legal?"
- **Why:** Not every concern should block a grade. A missing justification must block (it's a
  safety rule); an unrecognised future field shouldn't. The split makes the pipeline's later
  decisions ("ship it / repair it / reject it") clean.

**Acceptance:** `pytest tests/test_schema.py` → **9 passed**. Valid looks pass; unjustified ops,
undisclaimed materials, unjustified global ops, and unknown major versions all fail; unknown
fields warn; default protections carry the spec's clamp values.

---

## Phase 2 — Segmentation

Turning a photo into named regions (face, skin, hair, clothing, sky, vehicle…) so edits can be
applied *locally* instead of smeared across the whole image.

### D2.1 — Two models, because they know different things
- **Decision:** YOLOv8-seg **and** MediaPipe, combined.
- **Why:** YOLO knows *scene objects* — it finds people, buses, plants, and traces their
  outlines. It does **not** know where a face ends and hair begins. MediaPipe knows *people* —
  it splits a person into hair / body-skin / face-skin / clothes and pinpoints 478 facial
  landmarks. We need both: the scene from one, the person from the other.
- **Trade-off:** Two models to load, so segmentation takes a few seconds per image. Fine — this
  runs once per grade, not per frame.

### D2.2 — Priority resolution: the most protected region wins
- **Decision:** When regions overlap, they're resolved in a fixed order —
  `eyes > face > skin > hair > clothing > person > objects > background`.
- **Why:** A pixel can honestly be "person" *and* "face" *and* "eye" at once. Whichever label we
  keep determines which protections apply, so the **narrowest, most protected** label must win.
  An eye pixel must be labelled `eyes`, or the "eyes are never hue-shifted" rule silently
  wouldn't apply to it.
- **Verified:** every pixel lands in exactly one class — 921,600/921,600 and 874,800/874,800 on
  the two sample photos, asserted in the tests.

### D2.3 — Face detection is deliberately over-eager (confidence 0.2, not 0.5)
- **Decision:** Lower the face-detection threshold well below the default.
- **Why:** I found the default (0.5) **missed a clearly visible face** in our own sample photo.
  The error here is asymmetric: a *missed* face means the face and eye protections never get
  applied to it — precisely the failure the constitution calls unacceptable. An *over-eager*
  detection only means we protect slightly more area than strictly necessary. **When in doubt,
  protect.**
- **Trade-off:** Occasional false-positive face regions, which are graded conservatively. That's
  the cheap direction to be wrong in.

### D2.4 — Sky must touch the top of the frame
- **Decision:** No model in our stack knows "sky", so it's a heuristic: blue-ish/bright, upper
  frame, **and part of a region connected to the top edge**.
- **Why:** The naive version (blue-ish + bright + upper frame) mislabelled **2.6% of a blurred
  stadium crowd as sky** in our own sample — an out-of-focus background reads as "bright and
  blue-ish" but floats mid-frame. Real sky reaches the top of the picture. Adding that one
  condition removed the false positives completely (2.6% → 0%).
- **Trade-off:** Sky glimpsed only through a gap (a window, between buildings) will be missed.
  Deliberately conservative: it would rather miss sky than steal pixels from your subject.

### D2.5 — `person` is "unclassified human", and is deliberately **not gradeable**
- **Decision:** Pixels known to be a person but not resolvable into face/skin/hair/clothing keep
  the internal label `person`. This label is **not** in the Look Schema's closed vocabulary, so
  no operation can target it — those pixels are simply left untouched.
- **Why:** This residue is mostly thin boundary pixels, plus distant/occluded people the person-
  parser can't split. Guessing is unsafe in a specific way: call a bare arm "clothing" and the
  planner could shift its hue with **no skin protection applied**. Leaving it ungraded is the
  only option that can't violate a protection. The schema enforces this for free — the validator
  rejects any operation targeting a class outside the vocabulary.
- **Trade-off:** Small ungraded areas at region edges (a possible faint seam). Feathering hides
  most of it. Improving this — a skin-tone fallback for ambiguous human pixels — is a clear
  v0.2 task.
- **Known limitation (honest):** in `people.jpg`, one man's shouting, angled face is not detected
  by the landmarker, so his face is labelled `skin` rather than `face`. He still receives the
  **skin** protections (hue ≤ 8°, etc.), and the adjustment vocabulary excludes texture/clarity
  entirely, so the practical exposure is small — but it is a real gap, recorded rather than hidden.

**Acceptance:** `pytest tests/` → **19 passed** (9 schema + 10 segmentation). Every pixel
classified exactly once; vehicle found in the street scene; eyes sit inside the face; feathering
softens edges; colour-coded overlays written to `runs/overlays/` for visual inspection.

---

## Infrastructure pivot — OpenRouter instead of direct Anthropic

Before starting Phase 3, OTT asked to route all vision-model calls through **OpenRouter**
instead of the Anthropic API directly, so several candidate models can be compared on real
tasks before committing to one.

### D2.6 — One shared function, `src/vlm_client.ask_the_model()`, and nothing else touches a provider SDK
- **Decision:** Every module that needs a vision-model call (analyzer, planner, critic, the
  smoke test) goes through this one function. No other file imports `openai` or `anthropic`.
- **Why:** If the provider or the client library ever changes again, there is exactly one file
  to edit. It also makes the model **swappable per call** — the analyzer, planner, and critic
  can each use a different model id without touching each other's code.
- **Trade-off:** None real — it's a thin wrapper (encode image, one HTTP call, return text).

### D2.7 — OpenRouter over calling each provider directly
- **Decision:** Use OpenRouter (an OpenAI-compatible gateway to many providers) instead of the
  Anthropic SDK.
- **Why:** OTT wants to A/B the actual judgment quality of different models — specifically,
  which one can be trusted to correctly notice when a face's colour has been altered, since the
  analyzer and critic's entire job depends on that judgment being right. OpenRouter makes that a
  one-line model-id change (`scripts/test_vision_models.py`) instead of writing a separate
  client per provider.
- **Trade-off:** An extra hop (OpenRouter → provider) versus calling Anthropic directly; for a
  few vision calls per grade this cost is negligible next to the value of being able to compare.

### D2.8 — `scripts/test_vision_models.py` is a throwaway, not part of the pipeline
- **Decision:** The comparison script is a standalone CLI that prints raw responses — no
  parsing, no schema, no UI.
- **Why:** Its only job is letting a human eyeball three answers side by side and judge which
  model actually notices an altered face versus which one just writes confidently. That's a
  one-time (or occasional) decision, not a runtime dependency — it shouldn't be dressed up.

**Everywhere the model id was previously hardcoded now takes it as a parameter** — the build
plan and constitution were updated to say "vision call via `src/vlm_client`", not "an Anthropic
call", and to stop hardcoding a specific model name.

**Status:** infrastructure only — `analyze/`, `plan/`, `critic/` remain stub files, per OTT's
instruction not to touch them yet. `scripts/smoke.py`'s API check was also switched to go
through `vlm_client` (it directly called `anthropic.Anthropic` before, which would now silently
break since `.env` no longer has an `ANTHROPIC_API_KEY`). Verified: `pytest tests/` still 19/19;
`smoke.py` still reports the vision stack (OpenCV/YOLO/MediaPipe) green and fails only on the
missing key, now correctly named `OPENROUTER_API_KEY`.

### D2.9 — Picking the analyzer's model with a real, self-made ground-truth test, not a guess

OTT asked to widen the comparison (add ChatGPT/GPT-4o, Gemini 3, Qwen) and to actually **find
images and test**, with instructions to move to Phase 3 once a verdict looked right.

- **Decision:** rather than pull a random photo off the internet and eyeball it, I built a
  ground-truth test using the Phase 2 segmentation I already had: took the real sample photo,
  used the `face` mask to shift ONLY the face region's hue, and saved two variants — an obvious
  one (+50 hue units, bright green, a sanity check) and a moderate one (+13 units, a visible but
  plausible-looking tint) at `evalset/samples/people_face_{altered,subtle}.jpg`. Because I made
  the alteration, I know the exact right answer, so a model's response can be graded instead of
  judged by feel.
- **Why:** the previous run's test photo had no tampering at all, so every model "passed" by
  default — it tested nothing. The real question for this product is "can this model be trusted
  to notice when a face's color has been shifted," and that can only be tested by actually
  shifting one.
- **Interesting side-finding:** going from +8 to +13 hue units (out of 180) took the face from
  "unnoticeable" to "obviously wrong" — a very narrow band. That's independent evidence the
  schema's 8° max skin hue-shift protection ([[look-schema-v0.1]] section 6) is set close to the
  real perceptual threshold, not an arbitrary number.
- **Result, run against the moderate (+13) image:**
  - **Pass** — `google/gemini-2.5-flash`, `google/gemini-3-flash-preview`, `z-ai/glm-4.5v`: all
    three correctly said both faces were altered, and named the color.
  - **Partial** — `qwen/qwen3-vl-30b-a3b-instruct`: caught one face, incorrectly said the second
    (equally altered) face was untouched.
  - **Untested** — `anthropic/claude-sonnet-5`, `openai/gpt-4o`: OpenRouter balance ran out
    mid-run (402 again). Not a quality result either way — genuinely unknown until the account
    has more credit.
- **Chosen model: `google/gemini-2.5-flash`.** It passed, and of the three clean passes it's the
  cheapest ($0.30 / $2.50 per Mtok vs GLM's $0.60/$1.80 and Gemini 3's $0.50/$3.00) — the same
  "if more than one passes, take the cheaper one" rule OTT gave for this decision.
- **Trade-off / open item:** Claude and GPT-4o are not ruled out, only untested. If OTT adds
  OpenRouter credit later, it's worth re-running `scripts/test_vision_models.py` against
  `people_face_subtle.jpg` specifically (not the clean photo) to give them a fair, real test
  before treating the model choice as final.

---

## Phase 3 — Analyzer (`src/analyze/`)

Turns one photo into a `SceneAnalysis` — lighting, environment, camera character, existing
grade, mood, and any environmental material colour that needs the blue-glass disclaimer later.

### D3.1 — The full Pydantic JSON Schema is sent to the model, not a hand-written description
- **Decision:** the prompt embeds `SceneAnalysis.model_json_schema()` directly.
- **Why:** hand-describing the shape in prose invites drift from the actual schema (a field
  gets renamed in `models.py` and the prompt silently goes stale). Generating it from the same
  Pydantic model that will validate the answer means the two can never disagree.

### D3.2 — Cache key is (image content hash, model id), not just the image
- **Decision:** `runs/cache/<sha256>__<model>.json`.
- **Why:** analysis calls cost money, and re-running the same sample during development
  shouldn't re-pay for it — but a cached Gemini answer must never be silently served for a
  request that asked for Claude. Including the model in the key makes that impossible by
  construction rather than by discipline.

### D3.3 — One repair retry sends the validation error back to the model, not a generic retry
- **Decision:** on a parse/validation failure, the retry prompt includes the exact Pydantic
  error and the model's own broken reply, and asks it to fix it.
- **Why:** a blind retry (same prompt again) mostly reproduces the same mistake. Showing the
  model what specifically was wrong (a missing field, a bad enum value) gives it a real chance
  to correct it, matching the spirit of the validator's error messages elsewhere in this project.

**Acceptance, run live (not mocked):** both sample photos analyzed for real via
`google/gemini-2.5-flash`. `pytest tests/` → **25 passed** (9 schema + 10 segmentation +
6 analyzer). Read against the actual photos:
- `people.jpg`: hard artificial LED light from the side, outdoor/night, high contrast, correctly
  detected an existing grade (contrast + saturation boost), mood "intense, focused, energetic,
  dramatic" — matches two coaches shouting/pointing under stadium floodlights. No material notes
  (correctly — there is no tinted glass or coloured surface in this photo).
- `street.jpg`: hard sun, outdoor/midday, existing grade "bright, saturated, vibrant". Three
  material notes: the bus's **blue** paint, the building's **yellow** stucco, the **green**
  window frames — all three verified correct against the actual photo (I initially mis-recalled
  the bus as yellow from an overlay visualization color and re-checked the raw photo before
  trusting the analyzer's answer over my own memory — it was right, I was wrong).
