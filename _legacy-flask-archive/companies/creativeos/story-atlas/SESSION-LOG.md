# Story Atlas — Session Log & Handoff

> A complete record of the session that created Story Atlas, so you can pick the
> work back up **from your laptop** without the cloud session. Everything needed
> to understand, run, and continue the build is in this repo — this file is the
> map.
>
> **Session date:** 2026-07-24
> **Branch:** `claude/story-atlas-mvp-45lvjz` → merged into `master`
> **PR:** https://github.com/OTT55/ott-sovereign-stack/pull/3

---

## 1. What this session did

Added **Story Atlas** as **company #11** in the Sovereign Stack — a structured
operating environment for building, organizing, and maintaining fictional
universes (novels, films, TV series, games, animation). It is deliberately **not**
a notes app and **not** a generative writer. It treats a story as a *connected
system* and makes that graph intelligent.

New folder: **`companies/story-atlas/`**. Registered on **port 5109**.

---

## 2. How to resume from your laptop

```bash
# one-time: get the code onto your machine (local folder, NOT a synced drive)
git clone https://github.com/OTT55/ott-sovereign-stack.git
cd ott-sovereign-stack

# Story Atlas lives here:
cd companies/story-atlas
pip install -r requirements.txt
python app.py
# → open http://127.0.0.1:5109
```

To keep working: edit files here, commit, push. Start your next Claude Code
session pointed at this folder and hand it this file (`SESSION-LOG.md`) plus the
`README.md` — that's the full context.

If you ever pull and Story Atlas isn't there, make sure you're on `master`
(or the feature branch) and `git pull`.

---

## 3. The product, in one paragraph

Every story is a system of characters, events, locations, organizations, and
ideas. Story Atlas stores those as typed entities and wires them together with a
single `relationships` table (typed edges between *any* two entity types). Two
subsystems read from that one graph and make it smart:

- **Canon Engine (StoryDNA)** — continuously audits the universe for
  contradictions and names the exact records in conflict.
- **AI Assistant** — answers questions by *querying the graph*, not by inventing.

The interface feels like Notion/Linear/Obsidian: a sidebar of the universe, a
character database, a visual timeline, a force-directed relationship graph, and
the two intelligence panels.

---

## 4. Architecture & file map

House style matches the rest of the Sovereign Stack: **Flask + SQLite +
hand-written HTML/CSS/JS**, dark editorial aesthetic, `/__whoami` identity probe.

```
companies/story-atlas/
├── app.py                # Flask API + schema + seed data + Canon Engine + AI query engine
├── requirements.txt      # Flask==3.1.3
├── README.md             # product + feature overview
├── SESSION-LOG.md        # this file
├── .gitignore            # *.db, __pycache__/, .venv/
├── templates/
│   └── index.html        # single-page shell: sidebar + main + modal host
└── static/
    ├── style.css         # premium dark theme (one warm gold accent)
    └── app.js            # vanilla-JS SPA: views, force-directed graph, modals, assistant
```

**Data model (SQLite, one DB per install, gitignored):**
`universes`, `characters`, `locations`, `organizations`, `events` (timeline),
`scenes`, `lore`, `relationships` (typed edges), `scene_characters` (join).

The `relationships` table is the spine: `(source_type, source_id) →
(target_type, target_id, kind, label)`. Everything — graph, assistant, canon
checks — reads from it, so there is a single source of truth.

---

## 5. The seed universe — "Meridian"

A political sci-fi world seeded so the app is compelling on first run. Two
centuries after Earth seeded the Meridian system, three colony worlds fracture
over who controls the jump-gate connecting them. Calendar label: **AE** (After
Expansion); the story opens in AE 300.

**Characters:** Chancellor Aldric Vane (ruler), Mara Vane (adopted heir), Torix
Vane (rival nephew, fleet prefect), Dr. Sela Ondt (Ceres gate engineer), Admiral
Josa Halden (dead founder, historical).
**Locations:** Halden Station, Ardenne, Free Ceres.
**Organizations:** The Meridian Compact, Compact Gate Fleet, Free Ceres Movement.
**Timeline, scenes, lore, and a full relationship graph** are all seeded.

### Two DELIBERATE canon violations
The seed intentionally plants two contradictions so the Canon Engine has real
catches on first run (both titled `[demo flaw] …`):
1. A scene set in **AE 245** that includes **Mara Vane**, who isn't born until AE 266.
2. An event in **AE 250** that references **Admiral Josa Halden**, who died in AE 241.

Delete these two records (or fix the years) and the Canon Engine goes green.

---

## 6. Canon Engine — the checks it runs (all real)

Implemented in `canon_check()` in `app.py`:

1. **Impossible lifespan** — death year before birth year.
2. **Timeline contradiction** — a character in a scene set before their birth or after their death.
3. **Posthumous reference** — an event dated after a character's death that names them (matches on distinctive name tokens, titles stripped, to avoid false positives on names that double as places, e.g. "Halden Station").
4. **Broken connection** — a relationship whose endpoint entity no longer exists.
5. **Governance gap** — an organization with no leader on record.
6. **Orphaned character** — a character connected to no scene, event, or relationship.

Warnings are sorted error → warning → info, and each carries `refs` (the exact
records), which the UI turns into clickable chips.

---

## 7. AI Assistant — the intents it understands

Implemented in `ai_answer()` in `app.py`. A small intent parser maps a natural
question onto a real graph traversal:

| Ask something like… | It runs |
|---|---|
| "Show every scene involving Mara" | scenes-of-character |
| "Who has never met the Chancellor?" | set difference over shared scenes + direct relationships |
| "What happens if Aldric dies?" | impact analysis — every scene, tie, and org wired to him |
| "Who is connected to Torix?" | direct relationships |
| "Who leads the Gate Fleet?" | organization leadership |
| (just a name) | character profile fallback |

Returns cited records; empty results are themselves treated as a valid answer.

---

## 8. HTTP / JSON API surface

```
GET  /                                  single-page app
GET  /__whoami                          identity probe (for scripts/check_ports.py)
GET  /api/universes                     list universes
POST /api/universes                     create universe
GET  /api/universes/<id>/overview       dashboard counts + canon summary
GET  /api/universes/<id>/characters     character list
POST /api/universes/<id>/characters     create character
GET  /api/characters/<id>               character detail (+ relationships, scenes)
PUT  /api/characters/<id>               update character
GET  /api/universes/<id>/timeline       events (+ links)
POST /api/universes/<id>/events         create event
GET  /api/universes/<id>/locations      locations
GET  /api/universes/<id>/organizations  organizations (+ resolved leader name)
GET  /api/universes/<id>/scenes         scenes (+ characters present)
GET  /api/universes/<id>/lore           lore
GET  /api/universes/<id>/graph          nodes + edges for the relationship graph
GET  /api/universes/<id>/canon          full canon warning list
POST /api/universes/<id>/ask            AI assistant query  {q: "..."}
```

Configuration (all env-driven, sensible defaults): `STORY_ATLAS_PORT` (5109),
`STORY_ATLAS_DB` (story_atlas.db), `STORY_ATLAS_DEBUG` (0).

---

## 9. Registry wiring done this session

- `PORTS.md` — added `5109 | Story Atlas | companies/story-atlas/` to the Sovereign Stack 51xx block.
- `companies/run_all.py` — added `("story-atlas", 5109, …)` so it launches with the fleet.
- `README.md` (root) — Story Atlas listed as company #11; heading changed from "THE 9 COMPANIES" to "THE COMPANIES".
- `companies/README.md` — added the company #11 table row.

---

## 10. Bugs found & fixed during testing

1. **Blank year fields became `""`** instead of `NULL`, which crashed the Canon
   Engine's numeric comparisons (`str < int`). Fixed in the seed helper and in
   `api_create_character`; years now stay `None` when blank.
2. **Canon auditor made defensive** — added `as_year()` coercion so a stray
   non-integer year can never 500 the overview endpoint.
3. **Posthumous-reference false positives** — the surname "Halden" doubles as a
   station/dynasty name. The check now requires all distinctive name tokens
   (titles stripped), so only genuine references are flagged.

Verified end-to-end: every endpoint, both planted canon flaws flagged correctly,
all AI intents returning cited results, `app.py` compiles, `app.js` parses, and
visual confirmation via screenshots of the dashboard, graph, and assistant.

---

## 11. Roadmap — where to take it next

- **Create/edit parity** for locations, organizations, lore, and scenes (characters already have it).
- **Canon Engine impact preview** — apply a hypothetical ("the king dies in AE 300") and preview cascading warnings *before* committing the change. This is the killer "StoryDNA" feature.
- **Relationship editing UI** — add/remove edges from the graph directly.
- **Multi-user + real auth** — the schema is already per-universe; add ownership.
- **Export a universe bible** — PDF / production-doc export for a writers' room or studio.
- **Richer AI intents** — "who benefits if X and Y ally?", "which scenes have no conflict?", pacing/POV coverage checks.

---

*This log is the handoff. Clone the repo, open this folder, and everything above
is reproducible on your laptop with no dependency on the cloud session.*
