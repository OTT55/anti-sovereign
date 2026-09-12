# CreativeOS — Design System

One design language across five products. A creator should recognize CreativeOS instantly whether
they're in FrameVault or OTT Studio. Dark, precise, editorial — near-black surfaces, restrained
color, one confident accent.

---

## 1. Design tokens

```css
:root {
  /* Surfaces — the OTT global dark palette, identical across every product */
  --bg-0:      #0B0B0D;   /* app background — almost black, not true black */
  --bg-1:      #141417;   /* panels, rail, cards, nav */
  --bg-2:      #141417;   /* cards (same tier as bg-1 in the global scale) */
  --bg-3:      #1D1D22;   /* raised / hover / modals / dropdowns */
  --line:      #2C2C33;   /* hairline borders */

  /* Text */
  --text-hi:   #F5F5F4;   /* primary — never pure white */
  --text-mid:  #B8B8C0;   /* secondary */
  --text-lo:   #73737D;   /* tertiary / disabled / captions */

  /* Accent — CreativeOS's ecosystem accent. */
  --accent:      #2563EB;   /* royal blue */
  --accent-hi:   color-mix(in srgb, var(--accent) 78%, white);
  --accent-dim:  color-mix(in srgb, var(--accent) 14%, transparent);

  /* Per-product hue — each CreativeOS surface still gets its own identity,
     while --accent stays constant for shell-level interactive elements. */
  --framevault:  #4F46E5;   /* slate blue — identity   */
  --filmcrew:    #0891B2;   /* teal      — collaboration */
  --rightsforge: #65A30D;   /* lime      — rights marketplace (merges the old
                                storyforge/rightshub split — one product, two deal modes) */
  --creatorstack:#FF5C87;   /* rose      — contests */
  --studio:      #B47CFF;   /* light violet — workspace */

  /* Semantic — OTT global status colors */
  --ok:   #22C55E;
  --warn: #F59E0B;
  --err:  #DC2626;

  /* The one red every OTT app carries somewhere, independent of its accent. */
  --ott-signature: #D72638;

  /* Type — system stack, no render-blocking CDN fonts */
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --font-mono: "SF Mono", "JetBrains Mono", "Fira Code", ui-monospace, Menlo, Consolas, monospace;

  /* Radius & elevation */
  --r-sm: 8px;  --r-md: 12px;  --r-lg: 18px;  --r-full: 999px;
  --shadow: 0 8px 30px rgba(0,0,0,0.45);

  /* Spacing scale (4px base) */
  --s1:4px; --s2:8px; --s3:12px; --s4:16px; --s5:24px; --s6:32px; --s7:48px; --s8:64px;
}
```

> Updated to the ecosystem-wide global palette — see
> [`/design-system/OTT-DESIGN-CONSTITUTION.md`](../../../design-system/OTT-DESIGN-CONSTITUTION.md)
> for the full rationale and the cross-product accent registry. `--creatorstack` and `--studio`
> are prototype-only product hues with no shipped app behind them yet, left unchanged.

**Rule:** `--accent` (violet) is for *interactive* elements — buttons, links, focus. Per-product
hues are for *wayfinding* — the active rail item, a product's header accent, a badge. Never let a
product hue take over the interaction color, or the platform stops feeling unified.

---

## 2. Typography

| Role | Size / weight | Notes |
|---|---|---|
| Display | 32–40px / 650 | Page titles, hero |
| Heading | 20–24px / 620 | Section headers |
| Body | 15px / 420 | Default |
| Small | 13px / 440 | Secondary UI |
| Caption | 11–12px / 500, +0.02em tracking, uppercase | Labels, meta |
| Mono | 13px | Hashes, IDs, provenance, code |

Line-height 1.5 for body, 1.2 for display. Letter-spacing tightens as size grows.

---

## 3. Core components

- **Button** — primary (accent fill), secondary (bg-3 + hairline), ghost (text only). Radius `--r-sm`,
  height 36px, 13–14px label.
- **Card** — `--bg-2`, `--line` border, `--r-md`, `--s5` padding. Hover lifts to `--bg-3`.
- **Badge / Pill** — `--r-full`, caption type. Verification badge uses `--ok`; product badges use the
  product hue.
- **Avatar** — circle, `--r-full`, ring in the active product hue when it denotes context.
- **Rail item** — icon + label; active state = product hue left-bar + `--accent-dim` fill.
- **Input** — `--bg-1`, inset hairline, focus ring in `--accent`.
- **Command palette** — centered modal over a scrim; mono for shortcuts; grouped results by product.
- **Stat tile** — big number (`--text-hi`), caption label, optional delta in `--ok`/`--err`.
- **Notification row** — product-hue dot + text + timestamp; unread = `--accent-dim` background.

---

## 4. Motion

- Transitions: 140–200ms, `cubic-bezier(0.2, 0.7, 0.2, 1)`.
- Product-pane swap: 180ms cross-fade + 8px rise. The shell chrome never animates — it's the stable
  frame.
- Respect `prefers-reduced-motion`: disable transforms, keep opacity only.

---

## 5. Accessibility

- Body text contrast ≥ 4.5:1 against its surface; large text ≥ 3:1.
- Focus is always visible — a 2px `--accent` ring, never `outline: none` without a replacement.
- Interactive targets ≥ 36px.
- Color never carries meaning alone — pair product hues with labels/icons.

---

## 6. Voice

Confident, precise, un-hyped. The product describes what it does, not how revolutionary it is.
Verbs over adjectives. "Publish original IP" — not "Unleash your creative genius." This matches the
platform's thesis: trust is the product, and trustworthy things don't shout.

---

## 7. Addendum — the "Modernist Paper" structural pattern (FilmCrew, FrameVault, RightsForge, `app/`)

The tokens in §1 describe the dark-only `prototype/` shell. The products actually built since
(`filmcrew/`, `framevault/`, `rightsforge/`, and the newer `app/`) use a different *structural*
pattern — light theme by default with a persisted dark toggle, Space Grotesk for display type,
IBM Plex Sans/Mono for text and data — but as of the OTT global palette (see the constitution),
their color values are no longer a separate palette. Their light mode uses the OTT global **light**
neutrals, and their dark mode uses the exact same global **dark** neutrals as §1 above. The only
thing that varies per product, in either structural pattern, is the one accent.

```css
:root {
  --bg: #FAFAF8; --bg-sunk: #F1F1EE; --surface: #FFFFFF; --surface-2: #FFFFFF;
  --line: #DDDDD7; --line-strong: color-mix(in srgb, #DDDDD7 55%, #111114);
  --ink: #111114; --ink-soft: #555560; --ink-faint: color-mix(in srgb, #555560 60%, #FAFAF8);
  --accent: /* one accent per product — slate blue 4F46E5 (FrameVault), teal 0891B2 (FilmCrew),
               lime 65A30D (RightsForge) */;
  --r-sm: 8px; --r: 12px; --r-lg: 18px; --r-pill: 999px;
  --display: "Space Grotesk", "Segoe UI", system-ui, sans-serif;
  --text: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, Menlo, monospace;
}
:root[data-theme="dark"] {
  --bg: #0B0B0D; --bg-sunk: #0B0B0D; --surface: #141417; --surface-2: #1D1D22;
  --line: #2C2C33; --line-strong: color-mix(in srgb, #2C2C33 60%, #F5F5F4);
  --ink: #F5F5F4; --ink-soft: #B8B8C0; --ink-faint: #73737D;
  /* --accent stays the same hex as light mode — one identity, not two */
}
```

Pick the light-toggle structural pattern for creator tools people browse for hours; pick the
dark-only shell (§1) for infrastructure-feeling surfaces. Either way, colors come from the one
global palette. Full registry and cross-ecosystem rules (not just CreativeOS) live in
[`/design-system/OTT-DESIGN-CONSTITUTION.md`](../../../design-system/OTT-DESIGN-CONSTITUTION.md).
