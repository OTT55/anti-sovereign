# CreativeOS — App (design build)

The full CreativeOS app, implemented from the **Claude Design** import (`CreativeOS.dc.html` in the
"CreativeOS full course app" design project). This is the newer, richer vision: CreativeOS as a
**social + course platform** wrapped around the six products.

## How to run

Open `index.html` in any browser — it's a single, dependency-free file. No build, no server.

```
creativeos/app/index.html
```

(It loads IBM Plex / Space Grotesk from Google Fonts over the network for the intended type; offline,
it falls back to system fonts.)

## What's new vs. the earlier `../prototype/`

- **New "modernist" identity** — warm near-black grounds, terracotta accent (`#E5482D`), IBM Plex
  Sans + Space Grotesk + IBM Plex Mono. **Light and dark themes** with a toggle (persisted).
- **A social layer** — a **Home feed** (stories, composer, posts with like/comment/save/follow),
  **Reels** (vertical video with wheel/swipe navigation, mute, tags), and **Discover** (masonry grid).
- **A Learn surface** — courses taught by creators, with progress tracking.
- **Refreshed products** — FrameVault (Work / Reels / Provenance ledger / Reviews tabs), FilmCrew
  (AI-matched applicants), RightsForge (one rights marketplace, Assets/IP mode toggle — merges what
  were originally two separate destinations, StoryForge and RightsHub), CreatorStack (featured brief
  + leaderboard), OTT Studio (board + AI jobs + asset tray), Messages, Settings.
- **Fully responsive** — desktop rail + top bar; a mobile bottom-nav layout under 760px.

## Architecture

A real, dependency-free single-page app that mirrors the design's own structure:

```
state  →  renderVals()  →  view(V)  →  root.innerHTML  →  wire()
```

- **`renderVals()`** computes every screen's data and styles for the current state (ported almost
  verbatim from the design's component — same `PEOPLE`, `FEED`, `REELS`, `COURSES`, etc.).
- **`view(V)`** builds the HTML string for the active screen + overlays.
- **`wire()`** attaches event handlers from a per-render registry (`data-click` / `data-input` /
  `data-key` / `data-wheel` / hover), and render preserves input focus + caret across re-renders so
  typing in ⌘K, comments, and DMs feels native.

Everything runs off one `state` object, one theme, one identity — the "one platform" thesis, again.

## Verified

Headless (jsdom): all 11 destinations navigate and render, theme toggles dark↔light, ⌘K opens, feed
interactions (follow/like) update state — **zero JS errors**.

## Provenance

Imported from the Claude Design project **"CreativeOS full course app"** (`CreativeOS.dc.html`), which
was itself generated from `../prototype/`. Design canvas format (`<x-dc>` + a React-style component)
→ reimplemented here as a runnable, dependency-free app.

See [../ROADMAP.md](../ROADMAP.md) for where each of these surfaces goes next.
