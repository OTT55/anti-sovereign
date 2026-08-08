# ContextCore Engine

The real ContextCore technology — chunking, TF-IDF retrieval, confidence scoring,
citation-grounded answers, entity/relationship extraction, and knowledge-graph
construction — as a standalone, importable Python package. No Flask, no HTTP routes,
no templates. This is the **engine**; `companies/contextcore/app.py` is one possible
**app** built on top of it (a Flask UI), not the technology itself.

Ported from `companies/contextcore/app.py`, which had this same logic correctly
implemented but interleaved with Flask request handlers and a `g`-context SQLite
connection. Every algorithm here is unchanged — chunk boundaries, TF-IDF math,
confidence thresholds, and prompts are byte-for-byte the same — only the framework
coupling was removed.

## Why an engine, not an app

An app is a UI wrapped around some logic for one audience (a browser, in this case).
An engine is the logic itself: something you can import, script, test in isolation,
and put a *different* UI on top of later (CLI today, an API or a desktop app
tomorrow) without touching the core.

## Structure

```
src/contextcore_engine/
  chunking.py    tokenize + paragraph/sentence-aware chunking (pure, no deps)
  retrieval.py   TF-IDF index + cosine retrieval (pure Python, no ML deps)
  confidence.py  answer confidence from retrieval scores (top score + gap)
  generation.py  Claude-composed answers, entity/relationship extraction,
                 conflict detection — every function degrades to an honest
                 fallback (extractive answer, "skipped" note) with no API key
  graph.py       knowledge-graph construction + static SVG rendering (NetworkX)
  store.py       plain sqlite3 persistence, no request-context coupling
  engine.py      ContextCoreEngine — the single entry point tying it together
  parsers.py     multi-format ingest (PDF/DOCX/XLSX/PPTX/CSV/.eml -> plain text)
cli.py           command-line front end
tests/           pytest, real assertions against real retrieval — no mocks
```

## Run it

```
pip install -r requirements.txt
python cli.py ingest evalset/q3_report.txt --title "Q3 Report"
python cli.py list
python cli.py ask CX-XXXXXXXXXX "what happened to revenue this quarter?"
python cli.py ingest evalset/plan_a.txt --title "Memo A" --category planning
python cli.py ingest evalset/plan_b.txt --title "Memo B" --category planning
python cli.py ask-collection planning "when is the launch date?"
python cli.py graph CX-XXXXXXXXXX --out graph.svg
```

## Test it

```
python -m pytest -q
```

21 tests, all against real behavior (real TF-IDF scoring on real text, real chunk
boundaries, real confidence thresholds) — nothing mocked. Verified 2026-07-25 on
this machine: `python -m pytest -q` → 21 passed.

## What needs a live Anthropic API key/credit

`generate_answer`, `detect_conflict`, and `extract_entities_relationships` all call
Claude. Every one of them has a real, honest fallback when no key is set or the call
fails — an extractive answer built straight from the retrieved passages, or a
`*_note` field explaining exactly what didn't run and why. Nothing is faked to look
like a successful generative/extraction pass. This machine currently has no
`ANTHROPIC_API_KEY` set, so the generative/extraction/conflict paths in the tests
and the CLI run above are exercising the fallback path, not the Claude path — set
`ANTHROPIC_API_KEY` and re-run `cli.py ingest` / `ask-collection` to see the
generative path.

## What was deliberately left out of the engine

- `distribution_intelligence.py` (genre/tier seed constants for one Flask demo
  collection) — that's app-specific seed content, not engine technology.
- Flask routes, `render_template`, and the SQLite `g`-context pattern — those are
  the app's job, not the engine's.
