# Cinematic OTT

An **AI cinematic grading engine**. You give it a **reference** image (a screenshot with a
look you love) and a **target** image (your own photo). It figures out *why* the reference
looks that way — the lighting, the atmosphere, the materials, how the camera behaved — and
applies those **causes** to your photo. It never blindly copies colors, and it never
repaints pixels or touches faces destructively.

This is **Scene Reconstruction**, not a filter, not a LUT, not color transfer.

The full rules live in [`files/CLAUDE.md`](files/CLAUDE.md). The build order lives in
[`files/BUILD_PLAN.md`](files/BUILD_PLAN.md). The data format lives in
[`files/look-schema-v0.1.md`](files/look-schema-v0.1.md).

---

## How it's built (6 modules, kept separate)

```
src/
  schema/    the Look Schema + a validator            (Phase 1)
  segment/   finds people, faces, skin, sky, etc.     (Phase 2)
  analyze/   looks at an image, describes WHY          (Phase 3)
  plan/      decides WHAT to change, with reasons      (Phase 4)
  execute/   does the actual color math (no AI)        (Phase 5)
  critic/    grades the result, drives retries         (Phase 6)
evalset/     reference/target test pairs               (Phase 7)
cli.py       the command you run
```

The modules only ever talk to each other through one JSON format (the Look Schema).
The part that *thinks* (AI) is completely separate from the part that *edits* (math).
That separation is the point.

---

## Setup (one time)

This project uses **Python 3.13** (the ML libraries have ready-made installers for it).

```bash
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Then add your Anthropic API key:

1. Get a key at **console.anthropic.com → API Keys**.
2. Copy `.env.example` to a new file named exactly **`.env`**.
3. Paste your key after `ANTHROPIC_API_KEY=`.

The `.env` file is never committed to git.

---

## Running it

```bash
python cli.py --ref evalset/samples/ref1.jpg --target evalset/samples/t1.jpg
```

Each run writes everything it did to `runs/<timestamp>/` — the edited image, the plan it
made (`look.json`), and a full log of every change and *why* (`log.json`). The log is a
feature, not an afterthought.

> **Status:** built one phase at a time. See the checklist in `files/BUILD_PLAN.md`.
> Phase 0 (environment) first; the pipeline is wired end-to-end in Phase 6.
