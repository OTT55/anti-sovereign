# Story Atlas — Creative Intelligence Workspace

**Company #11 · Sovereign Stack · Port 5109**

> A structured operating environment for building, organizing, and maintaining
> any story. Notion + Obsidian + a studio production bible + a reasoning
> engine — for novelists, screenwriters, showrunners, game designers, and
> animation studios, as much as for memoirists, biographers, historians,
> journalists, and true-crime writers. Fiction or not, a story is a connected
> system either way.

Story Atlas is **not** a notes app and **not** a generative AI writer. It treats
every story as a *connected system* — characters, locations, organizations,
timeline events, scenes, and lore, all wired together by typed relationships —
and makes that graph intelligent.

```
python app.py   →  http://127.0.0.1:5109
```

## What's in the MVP

The first prototype ships the six things the product lives or dies on:

| # | Feature | What it does |
|---|---------|--------------|
| 1 | **Workspace / Universes** | Create and switch between universes ("My Film Universe", "My Novel", "My Memoir"). Each is an isolated world. |
| 2 | **Character database** | Notion-style database with identity, narrative drive (goals, motivations, fears, conflicts, arc), relationships, and story presence. Create, edit, and open any character. |
| 3 | **Timeline engine** | A visual chronological timeline of births, deaths, wars, discoveries, and political shifts — each event carrying its connections. |
| 4 | **Universe graph** | An Obsidian-style force-directed relationship graph. Characters, locations, organizations, and events as one draggable, living web. |
| 5 | **AI Assistant** | Answers questions by **querying the graph**, not by inventing: *"Show every scene involving Mara" · "Who has never met the Chancellor?" · "What happens if Aldric dies?"* |
| 6 | **Canon Engine (StoryDNA)** | Continuously audits the universe for contradictions and names the exact records in conflict. |

Also included: Locations, Organizations, Lore system, and a Scene database.

## The two intelligent subsystems are real, not mocked

Consistent with the rest of the Sovereign Stack, nothing here is faked.

**Canon Engine** runs genuine checks over the data:

- impossible lifespans (death before birth),
- a character present in a scene set before their birth or after their death,
- events that reference a character dated after that character's death,
- relationships pointing at entities that no longer exist,
- organizations with no leader on record,
- orphaned characters connected to nothing.

The seed universe (**Meridian**, a political-sci-fi world) intentionally ships
with **two planted contradictions** so the engine has something real to catch on
first run — a scene set before a character is born, and an event that references
a long-dead admiral. Open the **Canon Engine** to see them flagged with the
exact scene, character, and event in conflict.

**AI Assistant** parses the question's intent and maps it onto a real traversal
of the graph (scenes-of, who-has-met, impact-of-removal, connections-of,
leadership-of), then returns cited records. Ask *"what happens if Aldric dies?"*
and it traces every scene, relationship, and organization wired to him.

## Architecture

Matches the Sovereign Stack house style: **Flask + SQLite + hand-written
HTML/CSS/JS**, a dark editorial aesthetic, and a `/__whoami` identity probe so
`scripts/check_ports.py` can recognise it on its port.

```
app.py                 Flask API, schema, seed data, Canon Engine, AI query engine
templates/index.html   single-page shell (sidebar + main + modal host)
static/style.css        premium dark theme
static/app.js           SPA: views, force-directed graph, modals, assistant
```

The data model is graph-first: a single `relationships` table stores typed
edges between *any* two entity types `(source_type, source_id) → (target_type,
target_id)`, which is what makes the graph, the assistant, and the canon checks
all read from the same source of truth.

## Configuration

Everything reads from the environment; defaults let it run with zero setup.

| Variable | Default | Purpose |
|----------|---------|---------|
| `STORY_ATLAS_PORT` | `5109` | HTTP port |
| `STORY_ATLAS_DB` | `story_atlas.db` | SQLite file (gitignored) |
| `STORY_ATLAS_DEBUG` | `0` | Flask debug/reloader |

## Roadmap (next)

- Editable locations / organizations / lore / scenes (create+edit parity with characters)
- Multi-user + real auth (the schema is already per-universe)
- Export a universe bible (PDF / production doc)

## Done

- **Canon Engine impact preview** — the character edit form has a "Preview impact"
  button that applies the hypothetical inside an uncommitted transaction, runs
  the same `canon_check()` before/after, diffs the two, then rolls back — so
  you see exactly which contradictions a change like "the king dies in 300"
  would introduce (or resolve) before you ever commit it. Nothing is written
  unless you separately click Save.
- Local-first draft intelligence: coreference resolution, dependency-parse
  relation/event extraction, deterministic temporal reasoning (a "running
  clock" over relative dates), a NetworkX knowledge graph (centrality,
  shortest-path), and a narrative-state snapshot — see
  `LOCAL_AI_EVALUATION.md` for what was tested and what was rejected.
