# CreativeOS — Interactive Prototype

A self-contained, high-fidelity mockup of the full CreativeOS ecosystem: one persistent shell with
all **five products** built inside it. No build step, no dependencies.

## How to run

Open the entry point in any browser (double-click, or drag the file in):

```
creativeos/prototype/index.html   →  redirects into the app (home.html)
```

Everything runs over `file://` with relative paths — no server needed.

## Architecture — one shell, one design language (literally)

This is the platform thesis expressed as code. Two shared files are inherited by every page:

- **`assets/creativeos.css`** — the entire design system (tokens, type, components). One stylesheet =
  one design language.
- **`assets/shell.js`** — injects the persistent chrome (brand, top bar, product rail) and wires the
  cross-product surfaces (⌘K search, notifications, wallet, toasts) into every page.

Each product page ships **only its own content** (`<main class="pane" data-view="…">`) and pulls in
the shared shell. That's the "thin products, thick spine" principle made real.

```
prototype/
  index.html          Entry point → redirects to home.html
  home.html           Cross-product activity feed (the event-bus payoff)
  framevault.html     Identity layer — profile, portfolio, provenance, reviews
  filmcrew.html       Collaboration — hiring pipeline, applicants, talent discovery
  rightsforge.html    Rights marketplace — assets (licensing, royalty splits) + IP (deal terms),
                      one product, two deal modes (merges the earlier storyforge.html/rightshub.html)
  creatorstack.html   Competitions — challenges, briefs, leaderboard
  studio.html         Workspace — production board, asset tray, AI job panel
  settings.html       One account across all products
  assets/
    creativeos.css    Shared design system
    shell.js          Shared shell (nav, ⌘K, notifications, wallet)
```

## What it demonstrates

- **One shell, five products** — the rail switches products; the chrome is identical everywhere
  because it's literally the same injected code.
- **⌘K / Ctrl+K** — one search box spanning people, projects, IP, assets and challenges, grouped by
  product. Try `umber`, `halcyon`, `maya`.
- **One wallet** (profile menu, top-right) aggregating earnings from three products.
- **One notification stream**, product-colour-coded, with working "Mark all read".
- **Cross-product loops** — every product page names the event it emits (`hire.completed`,
  `asset.licensed`, `ip.optioned`, `challenge.won`, `project.published`) and how FrameVault + the
  spine react.

## Verified

All eight pages verified headlessly (jsdom): the shared shell injects correctly on every page —
correct active nav, full rail, command palette, notifications and wallet all present, with no script
errors. `shell.js` passes `node --check`.

## Design language

From [design-system.md](../docs/design-system.md): near-black surfaces, electric-violet signature
accent (`#7C5CFF`) for interaction, per-product wayfinding hues, single-theme dark (it's the brand).

## Where to go next

See [../ROADMAP.md](../ROADMAP.md) — per-product "make it grander" ideas, real-app UI/UX references
to copy, and the phased full-throttle build roadmap.
