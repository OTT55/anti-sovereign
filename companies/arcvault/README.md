# ArcVault — IP Arbitrage

**Sovereign Stack company #9 · Category: IP Arbitrage**

ArcVault treats intellectual property as raw material. Public-domain works are
free and infinite; their *value* is unlocked by re-forging them for new genres,
formats, and markets. This MVP is the adaptation engine at the heart of that
thesis: take the verbatim opening of a real public-domain short story and rewrite
it in a target genre — preserving plot and characters while completely
transforming voice, tone, and pacing — then show the original and the adaptation
side by side.

## What it does

1. Choose one of five real public-domain openings (verbatim from Project
   Gutenberg, sources cited in [`stories.py`](stories.py) — no paraphrasing):
   *The Oval Portrait*, *The Gift of the Magi*, *The Adventure of the Speckled
   Band*, *The Necklace*, *The Open Window*.
2. Pick a target genre: Noir, Sci-Fi, Children's, Thriller, or Satire.
3. ArcVault calls Claude (`claude-opus-4-8`) with a system prompt that requires it
   to keep every named character and plot beat while fully committing to the
   genre's conventions, and to output only the rewritten prose.
4. Read the two versions side by side and download the adaptation as `.txt`.

The genre definitions, system prompt, and API call live in [`adapt.py`](adapt.py).

## Credentials & the credit blocker

ArcVault makes a **real** Claude API call — nothing is faked. It needs:

```bash
pip install anthropic
set ANTHROPIC_API_KEY=sk-ant-...      # Windows (use `export` on macOS/Linux)
```

> This repo's Anthropic account currently has a **$0 credit balance**, so live
> adaptations return an API error. The app surfaces that error honestly in the UI
> rather than inventing an adaptation. Add credit at console.anthropic.com to run
> it end to end. (Per the portfolio's rule: build the real thing and surface
> blockers, never mock them.)

## How to run locally

```bash
cd companies/arcvault
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
set ANTHROPIC_API_KEY=sk-ant-...
python app.py
```

Open <http://127.0.0.1:5108>.

## Stack

- Backend: Python Flask; Anthropic Python SDK (`anthropic`)
- Content: verbatim Project Gutenberg excerpts (public domain), sources cited
- Frontend: hand-written HTML/CSS/JS, split-pane original/adaptation view
