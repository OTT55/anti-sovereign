# Local-first AI evaluation — findings and instructions

**Origin**: built while extending Story Atlas's draft-import pipeline
(`companies/creativeos/story-atlas/`) with real local NLP instead of more
regex, and evaluating local LLM runtimes as an alternative to always calling
the Claude API. This document reports what was actually tested — not
assumed — on this machine, and gives instructions for applying the same
approach to this company's own AI-relevant code, if it has any.

**Machine this was tested on**: Intel Core Ultra 7 155H, 15.4 GB RAM, Intel
Arc integrated graphics — no discrete GPU. This matters a lot below; several
tools are CUDA-first and simply don't fit this hardware class.

---

## Part 1 — Local NLP pipeline findings (verified, not assumed)

Built and tested directly in `companies/creativeos/story-atlas/app.py`:

| Stage | Tool | Status |
|---|---|---|
| Tokenizer, POS tagger, dependency parser | spaCy (`en_core_web_sm`) | **Working** — already installed for NER; the same model ships a full parser, not just entity recognition. |
| Named entity recognition | spaCy | **Working** — layered additively on regex heuristics; catches what regex misses (and vice versa — neither tier is strictly better). |
| Relation/event extraction ("SRL-lite") | spaCy dependency parse (subject/verb/object off the sentence root) | **Working** — catches event verbs by *lemma*, so "founded"/"founding"/"founds" all match, where a fixed regex string list only catches the exact inflections someone thought to enumerate. Verified: "was founding" (never in the regex list) correctly detected as an event via this path. |
| Relation extraction (alternative) | REBEL (`Babelscape/rebel-large`) | **Tested, rejected.** On a 3-sentence test passage, REBEL extracted exactly one relation triple — and got it wrong: it conflated "1847" (which belongs to a separate sentence about a king's death) with the Order's founding date ("three centuries ago," stated with no absolute year at all), producing a fabricated (Order of the Broken Crown, inception, 1847) triple. It also completely missed "Marcus Doyle gave Clara Whitfield the ledger," which the dependency-parse approach above extracted correctly. Model load alone took ~6s once cached (~59 minutes the first time, on an unauthenticated HuggingFace Hub connection) for a worse result than the free, already-installed dependency-parse method. Don't adopt this. |
| Coreference resolution | `fastcoref` (biu-nlp/f-coref, 90.5M params) | **Working, with a real caveat.** Confirmed correct on the canonical test case: "John entered. He looked around. The king greeted him." → `[John, He, him]` resolved as one entity. Resolves **pronouns** reliably. Does **not** resolve **nominal/definite descriptions** ("the old admiral" referring back to a named "Josa Halden") — that's a harder, distinct sub-problem in coreference research that fastcoref (like most coref systems) doesn't cover. Report this distinction honestly if you extend it — don't claim full coreference. |
| Coreference (alternative) | `coreferee` | **Rejected** — requires spaCy 3.1 + TensorFlow 2.5 (pinned in its own package metadata), both incompatible with the newer spaCy/Python already in use. Don't retry this one; it's a hard version wall, not a flaky install. |
| Coreference (rejected general model) | AllenNLP | **Rejected** — unmaintained since 2022, pulls ancient pinned dependencies that fail to build on Python 3.14 (`distutils.msvccompiler`, removed from modern Python). Don't retry. |
| Temporal reasoning | `dateparser` | **Rejected after direct testing** — resolves "ten years later" correctly but returns `None` for "ago"/"earlier"/"following" phrasing and even inverts direction on "a decade after" (tested against a fixed anchor date). Replaced with a small deterministic offset parser (number-word + unit + direction), which resolves all of the above correctly and chains a "running clock" across multiple relative references in reading order (verified: 1847 → "ten years later" → 1857 → "a century later" → 1957). |
| Knowledge graph | NetworkX | **Working** — already a transitive dependency of spaCy/thinc, but declared directly since the code imports it itself. Powers real graph-theoretic queries (degree centrality for "who's most connected," shortest-path for "how are X and Y connected," including indirect chains) instead of a flat relationship-table lookup. |
| Narrative-state snapshot | Built on existing SQL tables, no new dependency | **Working** — a `narrative_state(uid, as_of_year)` projection (alive/dead/not-yet-born, last-known location, current ties) built by walking the same tables the canon checker already does. Verified across three time points in a test universe. |

**Critical environment note for whoever picks this up**: the newest
`transformers` (5.x) has refactored internals that break `fastcoref`'s (and
likely other older HuggingFace-ecosystem tools') model loading with an
`AttributeError` on load, not an import error. If you add anything from this
ecosystem, pin `transformers==4.57.6` (confirmed working) rather than letting
pip resolve to the newest version.

**House convention followed**: everything above degrades honestly — a
missing/incompatible dependency returns an "unavailable" status with a real
reason, never a silent wrong answer or a crash. Same pattern as
ContextCore's `generate_answer()` (`companies/contextcore/app.py:130`).

---

## Part 2 — Local LLM runtime evaluation (tested on this machine)

| Runtime | Verdict |
|---|---|
| **Ollama** | **Tested live against the real `deepen_draft()` task, 3 runs.** `llama3.2:3b` (Q4_K_M, 2.0GB, already pulled). Valid JSON every run; correctly re-typed entities the first-pass got wrong (moved "Ember Hollow"/"Ravenmoor" out of characters into locations each time) with zero invented entity names. But on the one date requiring real inference with no stated anchor ("founded three centuries ago"), it gave a different, confidently-wrong specific year every single run (1023, 1863, 900) — never once said "unknown." One run also fabricated lore prose not in the source. Performance: 30-45s/call, 9-12 tok/s, 100% CPU (no Arc iGPU offload from Ollama 0.32.5), ~2.6GB resident — survivable but tight on this machine's free RAM. **Verdict: not a safe unattended replacement.** It's reliable at entity re-typing but confidently fabricates on exactly the "reason out relative dates" job this task needs — the opposite of this app's own honest-degradation design, where a null/failure is supposed to beat a plausible lie. Useful as a human-reviewed draft assist, not as an autonomous substitute for Claude. |
| **llama.cpp** (raw, not via Ollama) | **Not viable, confirmed.** `llama-cpp-python` has no prebuilt wheel for this platform, and its source tarball fails to unpack on Windows — llama.cpp's own bundled web-UI folder structure trips the 260-character `MAX_PATH` limit before any compilation even starts. CMake is also missing from PATH, a second blocker. Even if it built, quality/speed would be identical to Ollama (same underlying engine) — no upside, only friction. Don't pursue this over Ollama on Windows. |
| **LM Studio** | Has a genuine headless CLI (`lms`/`llmster`) — not GUI-only, confirmed via its own docs. Live testing stopped short of actually installing it: that's a download-and-execute action requiring the user's explicit permission in chat, which a background evaluation session can't obtain on its own. RAM is borderline-adequate for a 7-8B Q4 model (~4-5GB); Intel Arc gets a Vulkan backend but with inconsistent iGPU detection reported upstream — expect mostly CPU-bound inference. |
| **Jan** | Has a genuine headless serve mode in principle, but its CLI only gets installed by first launching the GUI app once — a bootstrapping step blocked for the same reason as LM Studio (needs the user's permission to install/launch). Not tested live. |
| **Open WebUI** | **Not relevant to this use case.** It's a chat front-end that sits in front of Ollama/any OpenAI-compatible API — not an inference engine itself. A backend Flask app calling an LLM programmatically has no use for a second chat UI; don't add this. |
| **LocalAI** | Docker-only on Windows (no `.exe`, confirmed from its own release assets) — not installed, and installing Docker Desktop is out of scope for a lightweight evaluation. Skip unless Docker is already part of this company's stack. |
| **vLLM** | **Not viable on this hardware, confirmed thoroughly.** CUDA-first by construction — its package ships kernel-autotuning tables keyed to specific NVIDIA GPUs. No usable CPU path (upstream-acknowledged threading regressions). Intel XPU path explicitly closed by vLLM's own maintainers for integrated Arc (lacks the required matrix hardware). Don't attempt this on any machine without a discrete NVIDIA/AMD GPU. |

**Bottom line**: of the seven, only Ollama was both installable without new
permissions and actually testable end-to-end — and the honest result is
mixed, not a win. It's genuinely good at mechanical fixes (entity
re-typing) and genuinely bad at exactly the kind of inference-under-
uncertainty this portfolio's "honest degradation" convention depends on
(it fabricates confident answers instead of saying "unknown"). Treat any
local small model the same way here: fine for drafts a human reviews,
not safe as an unattended stand-in for an API call whose whole value is
knowing when to say it doesn't know. llama.cpp and vLLM are hard "no"s on
this hardware; Open WebUI is the wrong category of tool; LM Studio, Jan,
and LocalAI all need an install this evaluation wasn't authorized to
perform on its own.

---

## Part 3 — Instructions for this company

If you're the session picking this up for **contextcore**, **canonchain**, or
a **CreativeOS sub-app**:

1. **Test the local runtime models against your own application** — not just
   this generic finding. Your app's actual task (retrieval-augmented
   generation, registry signing logic, whatever it is) may have very
   different quality requirements than Story Atlas's structured-JSON
   extraction task.
2. **Do not override your existing Claude API integration** until the user
   has checked this. Either keep it disabled/unmerged pending their review,
   **or** add a user-facing toggle so they can opt into the locally-tested
   runtime instead of it silently replacing what's there.
3. **Give a detailed report on how the local model actually helped** (or
   didn't) — concrete output comparisons, not just "it worked."
4. **Explicitly conclude one of three things, as a required part of your
   report**: (a) an API key is still needed for acceptable quality, (b) a
   local runtime is genuinely sufficient and worth wiring in, or (c) leave
   the app as-is — the added complexity isn't worth it for what this app
   actually needs. Don't leave this open-ended.

