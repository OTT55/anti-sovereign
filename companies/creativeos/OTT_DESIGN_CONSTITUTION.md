# The OTT Design Constitution

*A living design system for every OTT product — CreativeOS, StoryAtlas, and whatever comes next.
This is the fuller document the original design-language brief (`OTT_Design_Language_and_Claude_Prompt.md`)
asked for: not a component library, but the philosophy, the token system, the interaction model, and
the honest account of what's real versus aspirational today. Copy this file verbatim into any new
OTT product folder — it is written to be portable and self-contained.*

---

## 0. The one-sentence test

> **A user should recognize an OTT product without seeing the logo.**

Not from color alone — from the *shape* of the interaction: how state changes, how errors read, how
motion arrives, how much it tells the truth. Color is the signature. Structure is the fingerprint.

---

## 1. Philosophy — why this exists

**Software that respects thinking.** Every OTT product should feel calm, focused, intelligent,
premium, cinematic, intentional. Never playful for its own sake. Never cluttered. Never "corporate
dashboard." The target feeling is closer to a premium magazine or a film title sequence than to
enterprise software.

> "Powerful enough for professionals. Calm enough to disappear behind the work."

Study why Apple, Linear, Notion, Arc Browser, TikTok, Instagram, Figma, and Stripe feel cohesive —
not their aesthetics, but the underlying discipline: one visual grammar, applied without exception,
so consistency itself becomes the trust signal. Do not copy their looks. Extract *why* they feel
inevitable, then apply that same discipline to something unmistakably OTT.

---

## 2. Psychology — the feeling each screen must produce

| A user should feel | Not |
|---|---|
| In control of a state change they triggered | Something happened automatically, off-screen |
| Told the truth about what's real | Reassured by something simulated |
| Oriented — this looks like the last OTT product I used | Starting from zero in a new app |
| That slowness is honesty, not sluggishness | Rushed by fake progress bars |

The single biggest driver of trust across the OTT ecosystem is **radical honesty in interface
state** (§8). Calm is not a visual style — it's the byproduct of never lying to the user about what
the software just did.

---

## 3. Brand system — one language, one accent per product

**Rule:** one shared design language across every product. Each product gets **exactly one**
signature accent color; everything else is a shared neutral system (graphite / black / off-white /
warm gray). This is not a suggestion — it is enforced today across five live CreativeOS products by
literally sharing the same CSS token *names* and structure, with only the accent value differing:

| Product | Accent | Role |
|---|---|---|
| FrameVault | Terracotta (`#C63A22` light / `#E5482D` dark) | Identity anchor — deliberately its own warm grounding, not the flat neutral (see the exception below) |
| FilmCrew | Teal (`#0891B2` / `#4E9BFF`) | Collaboration |
| RightsForge | Lime (`#65A30D` / `#E3A83A`… *actually gold-lime, see note* ) | Marketplace |
| CreatorStack | Rose (`#DB2777` / `#F0479A`) | Competitions |
| OTT Studio | Violet (`#7C3AED` / `#9F6BF2`) | Workspace |
| *(reserved)* | `--ott-signature: #D72638` | The brand mark itself — **never** used as a UI accent |

**The FrameVault exception, stated as a rule:** the product that anchors identity for the whole
ecosystem may keep its own grounding palette instead of the shared flat neutral — it is the one
place "distinct" outranks "consistent," because it is the root everything else points back to.
Every *satellite* product inherits the shared neutral system without exception.

**Anti-pattern:** giving a product a second accent for "variety," or reusing another product's
accent. One product, one color. If a product needs semantic color (success/warning/danger), those
are a *separate*, ecosystem-wide token set — never drawn from the accent palette.

---

## 4. Visual language — the token system, verbatim

This is the actual system running in production today (`companies/creativeos/*/static/*.css`). Define
a handful of primitives; derive everything else with `color-mix()` so the palette stays mathematically
consistent instead of hand-picked shade by shade.

```css
:root{
  /* Shared neutral primitives — identical across every satellite product */
  --bg:#FAFAF8; --bg-sunk:#F1F1EE; --surface:#FFFFFF; --surface-2:#FFFFFF;
  --line:#DDDDD7; --ink:#111114; --ink-soft:#555560;

  /* Derived, not hand-picked */
  --line-strong: color-mix(in srgb, var(--line) 55%, var(--ink));
  --ink-faint:   color-mix(in srgb, var(--ink-soft) 60%, var(--bg));

  /* The one thing that changes per product */
  --accent: #0891B2;   /* <- swap this line only */
  --accent-ink:  #FFFFFF;
  --accent-soft: color-mix(in srgb, var(--accent) 14%, var(--surface));
  --accent-line: color-mix(in srgb, var(--accent) 40%, var(--line));

  /* Semantic — ecosystem-wide, never the accent */
  --good:#22C55E; --warn:#F59E0B; --danger:#DC2626;

  /* Shape */
  --r-sm:8px; --r:12px; --r-lg:18px; --r-pill:999px;
  --shadow:0 1px 2px rgba(20,18,10,.05), 0 8px 28px rgba(20,18,10,.08);
}
:root[data-theme="dark"]{
  --bg:#0B0B0D; --surface:#141417; --ink:#F5F5F4; --ink-soft:#B8B8C0;
  --line:#2C2C33;
  /* accent gets a brighter dark-mode value; everything else re-derives automatically */
}
```

**Rule:** a new product's stylesheet should differ from this file in almost nothing but the accent
hex values (light + dark) and the product-specific component blocks. If you find yourself hand-tuning
a neutral shade, stop — derive it instead.

---

## 5. Typography

Prefer sentence case, short headings, clean hierarchy, editorial spacing. Avoid excessive ALL CAPS.
The ecosystem is building toward a custom OTT type system — **name it now, ship real fallbacks,
swap the truth in later without touching a single component:**

```css
--display: "OTT Sans Display", "Space Grotesk", "Segoe UI", system-ui, sans-serif;
--text:    "OTT Sans Text",    "Plus Jakarta Sans", "Segoe UI", system-ui, sans-serif;
--mono:    "OTT Mono",         "IBM Plex Mono", ui-monospace, Menlo, monospace;
```

**Honest status:** "OTT Sans" and "OTT Mono" do not exist as shipped typefaces yet — every OTT
product today renders on the fallback (Space Grotesk / Plus Jakarta Sans / IBM Plex Mono, all
real, licensed, loaded via Google Fonts). That's intentional and fine: the *name* is reserved in
every stylesheet so that shipping a real custom face later is a font-file swap, not a rewrite.

---

## 6. Motion — explains relationships, never decorates

```css
--ease: cubic-bezier(.2, .7, .2, 1);
@keyframes rise{ from{opacity:0; transform:translateY(10px)} to{opacity:1; transform:none} }
.wrap{ animation: rise .32s var(--ease); }
```

One named easing curve. One entrance animation, applied to the page content wrapper on every product
— a calm, consistent "arrival," not a flourish. Beyond that: **motion must reveal hierarchy, show
connections, or preserve context — never decorate.** State-change animation (a step lighting up, a
toast rising) is welcome; spinners and progress theater that don't correspond to a real, observable
change are not.

---

## 7. Accessibility & motion standard

Copy this block verbatim into every product's stylesheet — it already is, in five of them:

```css
:focus-visible{ outline:2px solid var(--accent); outline-offset:2px; border-radius:4px; }
@media (prefers-reduced-motion: reduce){
  *, *::before, *::after{
    animation-duration:.001ms!important; animation-iteration-count:1!important;
    transition-duration:.001ms!important; scroll-behavior:auto!important;
  }
}
```

Focus is always visible, in the product's own accent — never suppressed. Reduced-motion is a full
opt-out, not a partial one.

---

## 8. Radical honesty in interface state (the load-bearing principle)

This is the OTT ecosystem's sharpest, most consistently enforced rule, and it is worth stating on
its own: **never simulate something that didn't happen.**

Concretely, as built:
- FrameVault fingerprints a file **in the browser** and only ever sends the hash — never claims to
  "store" or "protect" the file itself.
- OTT Studio's AI jobs are a real, honestly-labelled **state machine** (`queued → running → done`),
  advanced by an explicit human click — never a fake progress bar pretending a model ran when none
  exists.
- FilmCrew's contracts and RightsForge's deals use the identical pattern: every state transition is
  explicit, human-triggered, and visually staged as a stepper — never silent, never automatic.
- Every credit that lands on a FrameVault profile is real, signed, and independently verifiable at
  `/verify` — never a hard-coded "reputation" number.
- Seeded demo data is labelled as seeded in code comments and never dressed up as live activity a
  user could mistake for their own history.

**Anti-pattern:** any UI element that implies computation, verification, or delivery happened when it
did not. If a feature isn't built yet, the honest options are: don't show the control, or show it
disabled with a true reason — never a control that quietly does nothing or fakes success.

This is also **why the interaction pattern repeats everywhere**: an explicit stepper the user
personally advances is the interface expression of "we don't do things behind your back."

---

## 9. Interaction model — the shared component vocabulary

Beyond tokens, the actual HTML/CSS class vocabulary is shared verbatim across products:
`.nav` / `.brand` / `.card` / `.badge` / `.btn-primary` / `.stat` / `.modes` / `.flow.step` /
`.result` / `.toast`. Learn one CreativeOS product's UI and you structurally know every other one.
Concretely:

- **Stepper pattern** (`.flow` / `.step` / `.bub`): any multi-stage real-world process — a contract,
  a deal, a job — renders as a horizontal stepper with done/now/pending states. Never a bare status
  string when the underlying thing has stages.
- **Result panel** (`.result` / `.result.plain`): the outcome of a significant action (a payment
  landing, a credit being written) gets its own highlighted panel with a clear next action — not a
  toast alone, when the action was consequential.
- **Toast** (`.toast`): for everything else — acknowledgement, not consequence.
- **Stat tile** (`.stat`): a number, a label, nothing decorative. Numbers are `font-variant-numeric:
  tabular-nums` so they don't jitter when they update.

---

## 10. Connected knowledge — the brand *is* the graph

Every OTT product should visualize relationships; information is never stored in isolated pages.
Concretely, this is not a visual metaphor in CreativeOS — it's the actual architecture: **FrameVault
is the identity every other product writes back to.** A hire in FilmCrew, a license in RightsForge, a
win in CreatorStack, a publish in OTT Studio — each is a different product, a different database, and
each one makes a *single, shared* identity richer. The public FrameVault page is the graph made
visible: one person, every credit, cross-linked back to where it happened.

**Rule for future products:** if a product creates a real-world outcome (a transaction, an award, a
publish) that outcome must write a verifiable credit back to identity. A product that doesn't connect
back to the graph is a silo, not an OTT product.

---

## 11. Product architecture — the isolation rule this all sits on

- Every product is its own service: own folder, own database, own port. No product ever opens
  another product's database file.
- Products talk to each other over HTTP with a shared service key — never a shared table.
- Identity is a service, not a feature: **one login, many apps**, exactly like Google. A satellite
  product verifies credentials via the identity product's `/api/authenticate` and never stores a
  password of its own.
- A satellite product's ordinary session identifies *who*, not *what they're allowed to do* — coarse
  membership/role checks live in the product itself for now; fine-grained cross-product permissions
  are a shared spine service to build later, not something each product should invent separately.

*(Full rationale, the scaling path, and the founder FAQ live in
`companies/creativeos/framevault/ARCHITECTURE.md` — CreativeOS-specific, not required reading to
apply this constitution elsewhere.)*

---

## 12. AI behavior guide — for whoever (human or Claude) builds the next OTT product

- **Disclose AI involvement, always, in the product's own voice** — FrameVault's AI-disclosure field
  is not a compliance checkbox, it's the trust feature. Every future product that touches generated
  or AI-assisted content needs an equivalent, visible, in the same honest register.
- **Never let an AI action look identical to a human one** without saying so. If a job, a
  recommendation, or a summary was AI-produced, label it at the point of display, not in a settings
  page nobody visits.
- **State machines over black boxes.** When you're tempted to have "AI do a thing" invisibly, prefer
  exposing it as an explicit, inspectable state the user advances or can watch (§8) — it's both more
  honest and more OTT.
- **Don't build a feature AI will trivially replace.** Bias every product toward identity, trust,
  ownership, coordination — the things that get *more* valuable as generation gets cheaper, not less.

---

## 13. Anti-patterns — do not do these

- A second accent color "just for this one button."
- A hand-picked neutral hex that isn't derived from the shared primitives.
- A progress indicator with no real, observable state behind it.
- Reusing `--ott-signature` as a UI accent — it's the brand mark, not a fifth product color.
- ALL CAPS body copy, enterprise-dashboard density, decorative icon soup.
- A new product that skips the shared component vocabulary and invents its own card/badge/button
  shapes "to be different." Different is the accent color. Nothing else.
- Any control that implies something happened when it didn't (§8) — the single most important rule
  in this document.

---

## 14. Honest gaps — what this constitution asks for that isn't true yet

Stated plainly, on purpose, because pretending otherwise would violate §8:

- **No real custom typeface yet.** "OTT Sans" / "OTT Mono" are reserved names on top of licensed
  fallbacks (Space Grotesk, Plus Jakarta Sans, IBM Plex Mono). Commissioning or designing the real
  faces is future work.
- **No icon family yet.** The brief calls for "one icon family"; today's products lean on a small,
  informal set of emoji glyphs as placeholders for icons. This should be replaced with a real,
  designed icon system before the ecosystem is considered visually complete.
- **Theme preference doesn't yet persist across products.** Each product runs on its own port/domain
  today, and browsers scope `localStorage` per-origin — so "dark mode" set in FrameVault doesn't
  currently carry into FilmCrew even though both read the same `cos-theme` key. The real fix is a
  server-side preference on the shared identity (FrameVault), read by every product on login — not a
  cookie hack. Worth building once there's a real multi-product user base to notice the seam.
- **Fine-grained cross-product permissions** (§11) don't exist yet; today's access control is
  per-product membership only.

A future editor of this document: when any of the above becomes true, move it out of this section
and into the relevant chapter above, with the same honesty this section models.

---

*This document supersedes nothing in `OTT_Design_Language_and_Claude_Prompt.md` — it answers that
brief's own closing request for "a living constitution with chapters, rationale, examples, rules,
anti-patterns, and implementation guidance," grounded in what is actually running in production
across CreativeOS today rather than written in the abstract.*
