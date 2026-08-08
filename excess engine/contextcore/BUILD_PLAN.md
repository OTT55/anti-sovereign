# ContextCore Engine — Build Plan

Honest gap analysis against `CLAUDE.md` (the constitution), and the phase order
to close it. Each phase ships something real and independently testable — no
placeholders, no stub engines that return canned data.

## Where the current code actually sits against the 8 engines

What exists today (`src/contextcore_engine/`) was ported from the old Flask app.
It's real, but it only covers pieces of three of the eight engines, and the
module layout doesn't yet mirror the architecture — everything sits in one flat
package instead of eight independently-testable engines.

| Constitution engine | Current state |
|---|---|
| **1. Ingestion** | Partial. `parsers.py` handles PDF/DOCX/XLSX/PPTX/CSV/EML → text; `chunking.py` does paragraph/sentence-aware chunking. **Missing:** OCR, metadata extraction (author, dates, source), version detection, duplicate detection, language detection. |
| **2. Knowledge** | Partial. `generation.extract_entities_relationships()` pulls entities + relationships via Claude at ingest time. **Missing:** ontology (entity types are free-text, not a maintained registry), terminology normalization, real duplicate-entity resolution (today's dedup is exact `(name, type)` string match — "Acme Corp" and "Acme Corporation" become two nodes). |
| **3. Context** | **Does not exist.** `retrieval.py` (TF-IDF) is a retrieval subsystem, not an organizational mental model — it has no concept of vocabulary, department structure, or which concepts are central to the org. |
| **4. Memory** | Minimal. `store.py` persists documents/chunks/entities/relationships in SQLite. **Missing:** embeddings, summaries, conversation history, document version history, relationship history over time, timeline. |
| **5. Reasoning** | **Does not exist.** `engine.ask()` is single-hop: retrieve top-k, generate one answer. No comparison, timeline, or multi-hop reasoning. |
| **6. Verification** | Partial. `confidence.py` (score + gap) and `generation.detect_conflict()` (cross-document contradiction check) are real and honest (never fabricate, always say when a check didn't run). **Missing:** ambiguity detection, explicit reasoning-path explanation, "missing evidence" as its own signal distinct from low confidence. |
| **7. Intelligence** | **Does not exist.** Nothing proactive — the engine only responds to questions, never surfaces gaps/risks/anomalies on its own. |
| **8. Domain** | **Does not exist.** No per-workspace ontology or extraction-rule specialization; every document uses the same generic extraction prompt regardless of domain. |

`retrieval.py` and `store.py` are shared infrastructure several engines lean on,
not engines themselves — the constitution's "retrieval serves reasoning" point
means retrieval stays a subsystem, not Engine 3.

## Proposed phase order

Each phase is scoped to not need anything the previous phase didn't already
provide, and — same discipline as `companies/cinematic ott/` — runs its own
tests before moving on.

**Phase 1 — An explicit public interface.** ← *built, 131 tests*
The stated goal was "wired through explicit interfaces instead of flat-package
imports", and that is what shipped: `contextcore_engine/__init__.py` now exports
all eight constitutional engines, so a caller writes
`from contextcore_engine import resolve` and never learns which file it lives
in. `tests/test_public_api.py` makes the promise real — if a module moves the
tests still pass, and if the *interface* changes they fail.

**What was deliberately not done, and why:** the phase also proposed moving the
modules into `engines/ingestion/`, `engines/knowledge/` and so on. That was
skipped. The modules were already independently testable — separate files,
separate test files, no circular imports — so the move would have been fourteen
file relocations and eight test-import rewrites for navigability alone, risking
a working 131-test engine for no capability. The interface delivers the phase's
actual purpose; the folder layout was cosmetics wearing its clothes.

**Phase 2 — Complete the Ingestion Engine.** ← *built, 61 tests*
Add: file-hash duplicate detection, metadata extraction (source filename, byte
size, ingested-at timestamp — real, no external dependency), simple statistical
language detection (stopword-overlap heuristic, no ML dependency), and version
detection (same title + high text-similarity to an existing doc → linked as a
new version, not a duplicate document). OCR is deferred — it needs the
Tesseract binary installed on the machine, a real external dependency the
constitution itself flags as "future." No API key needed for any of this.

**Phase 3 — Knowledge Engine: real entity resolution.** ← *built, 61 tests*
Replace exact-string entity dedup with a resolution step (normalize casing/
whitespace, then fuzzy-match candidates above a similarity threshold) and a
maintained ontology table (canonical entity → known aliases, entity type
registry) instead of ad hoc free-text types. This is the one place the
constitution explicitly calls out as missing today ("resolve duplicate
entities," "maintain canonical definitions"). Needs a live Claude key only for
the extraction step that already existed; resolution itself is deterministic.

**Phase 4 — Memory Engine: versions and timeline.** ← *built, 126 tests*
Extend `store.py` to keep document version history (from Phase 2's version
detection) and a relationship-history log (when a relationship was first seen,
whether it still holds), so "what changed between V4 and V9" has real data to
answer from. No embeddings yet — TF-IDF remains the retrieval layer; adding a
real embedding index is a Phase 6 scale decision, not a Memory-Engine
correctness one.

**Phase 5 — Context Engine.** ← *built, 126 tests*
Build the organizational mental model on top of Memory: corpus-wide term
frequency to surface central concepts, department/entity co-occurrence to
answer "which departments interact most," and a foundational-document score
(documents most referenced by / related to other entities in the graph). This
is the first genuinely new engine, not a refactor of existing code.

**Phase 6 — Reasoning Engine.** ← *built, 126 tests*
Multi-hop questions on top of Phases 4–5's data: version comparison ("what
changed between V4 and V9"), gap analysis (entities/relationships mentioned in
one document but never elaborated elsewhere), cross-document synthesis. Needs
a live Claude key to compose multi-step answers — will be built with the same
honest-fallback discipline as `generation.py` today.

**Phase 7 — Verification Engine: ambiguity + reasoning path.** ← *built, 126 tests*
Add explicit ambiguity detection (the corpus has multiple similarly-worded but
distinct entities matching a query term) and surface the reasoning path (which
documents/entities/relationships fed into an answer) rather than just the
confidence score.

**Phase 8 — Intelligence Engine.** ← *built, 126 tests*
A proactive scan job (run on demand or on a schedule) that walks the graph and
flags: contradicting policies, entities mentioned once and never followed up,
documents nobody has referenced recently. This is the first engine that
doesn't wait for a question.

**Phase 9 — Domain Engine.** ← *built, 126 tests*
Per-category (workspace) ontology and extraction-rule overrides — the same
Claude extraction call, but with a domain-specific prompt/entity-type set
swapped in per category, so a "legal" workspace and a "film" workspace extract
different things from the same underlying pipeline.

## Status

Constitution and this plan written 2026-07-25. **Nothing past Phase 0 (the
existing ported code) has been built yet.** Per the working rhythm that's
worked well on `companies/cinematic ott/`: one phase at a time, real tests
before moving on, explain the result in plain language, then stop and wait —
same here. Waiting on OTT to confirm the phase order above (or reprioritize)
before starting Phase 1.
