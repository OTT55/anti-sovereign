# CreativeOS — Analysis, "Go Grander" Ideas & Full Roadmap

A working document for analysing each product, deciding how far to push it, and stealing the best
UI/UX from apps that already solved similar problems. Written to be argued with — challenge
anything here.

**How to read this**
- **Built** = what exists in the prototype right now (`prototype/`).
- **Go grander** = the ambitious version, if you go full throttle.
- **Steal from** = real apps whose specific UX patterns are worth copying, and *what* to copy.
- **Roadmap** = Now (0–3 mo) / Next (3–9 mo) / Later (9+ mo).

---

> **Companion doc:** [STRATEGY.md](STRATEGY.md) is the standalone positioning argument (thesis, wedge,
> moat, the 60-second pitch) — read that for *why*; read this for *what to build and in what order*.
> V1 below is organized around that doc's AI-era trust wedge.

## 0. Ecosystem strategy (read this before the products)

### The one rule: spine before surface
The moat is the shared spine — identity, payments, reputation, provenance, permissions, the event
bus. Every "grander" idea below is only cheap to build because the spine already exists. If you're
ever unsure what to build next, **build the spine capability that unlocks the most products at
once**, not the flashiest single-product feature.

### The "magic moments" that prove the platform
These cross-product chains are the demo that makes an investor or university lean in. Prioritise them
— they're the entire reason not to build six separate apps:

1. **Win → funded → hired → paid → credited.** A CreatorStack win funds a production, you staff it
   in FilmCrew, deliver in OTT Studio, get paid to one wallet, and it all lands on your FrameVault —
   without re-entering anything.
2. **License → royalty → reputation.** A RightsForge license auto-splits money and quietly builds the
   seller's reputation graph.
3. **One search, one identity, one balance.** ⌘K spans everything; the wallet aggregates four income
   streams; your profile is the same object everywhere.

### AI strategy (your stated philosophy, made concrete)
Build around identity/trust/ownership/coordination; let AI do the mechanical work *inside* products.
- **Do build:** provenance + AI-disclosure (FrameVault), AI job orchestration (OTT Studio),
  semantic matching (FilmCrew/RightsForge), smart search ranking, fraud/authenticity checks.
- **Don't bet the company on:** generating the script/edit/track itself. That's the commoditising
  layer — support it, don't depend on owning it.

---

## 1. FrameVault — the identity layer

**Built:** verified profile, aggregated stats, skills, provenance-tagged portfolio, auto-updated
project history, AI-contribution disclosure, reviews earned through real transactions.

**Go grander**
- **The reputation graph as a real asset.** Weighted, decay-aware score computed from
  `reputation_events`, with a public methodology page. Reputation that's *explainable* is a
  differentiator vs. vanity follower counts.
- **Verifiable credentials / provenance receipts.** Every portfolio piece links to a signed
  provenance record (content hash + timestamp + contributors). This is your Canonchain/Veridact DNA
  folded in — "proof of authorship" becomes a feature, not a separate company.
- **Public creator pages as the top of the funnel.** `/@handle` pages that are genuinely
  beautiful and SEO-indexed become your organic acquisition channel — every creator markets the
  platform by sharing their page.
- **AI-contribution transparency as an industry standard.** Push the disclosure format as something
  studios *require*. Trust infrastructure that others adopt is a moat.

**Steal from**
- **Read.cv / Contra** — clean, editorial creative profiles; the anti-LinkedIn aesthetic. Copy their
  restraint and typographic profile layout.
- **LinkedIn** — the "activity auto-populates your profile" mechanic (but do it tastefully).
- **GitHub profile / contribution graph** — proof-of-work visualised; adapt for a "creative
  contribution" graph.
- **Behance / ArtStation** — portfolio grid density and project case-study pages.
- **Verified checkmark systems (Stripe Identity)** — verification as a trust primitive.

**Roadmap** — *Now:* real profile edit + public `/@handle` page. *Next:* computed reputation graph +
provenance receipts. *Later:* verifiable credentials, studio-adopted AI-disclosure standard.

---

## 2. FilmCrew — the collaboration layer

**Built:** production pipeline board, open roles, ranked applicants, talent discovery, the
`hire.completed` loop.

**Go grander**
- **AI-assisted crew matching.** Rank applicants by fit (skills + availability + reputation +
  past-collab graph), not just a list. The matching quality is the product.
- **Contracts + escrow for real.** Milestone-based escrow (Stripe Connect), e-signature, automatic
  release on delivery. This is the trust that lets strangers work together.
- **Availability calendar + scheduling.** Shared shoot calendars, call sheets, day-of coordination.
- **Team templates.** "Assemble a 6-person short-film crew" → suggested roles pre-filled.

**Steal from**
- **Mandy.com / Backstage / Stage 32** — the incumbents for film crew/talent. Study their role
  taxonomy and casting-call flows; then out-design them (they look dated — your opening).
- **Contra / Upwork / Braintrust** — freelance hiring, contracts, escrow, milestone payments.
- **Linear / Trello / Notion** — the kanban pipeline board interaction (drag-drop, quick-add).
- **LinkedIn Recruiter** — applicant ranking and shortlisting UX.
- **Deel** — contractor contracts + compliant global payouts.

**Roadmap** — *Now:* project + role posting, applications, shortlisting. *Next:* escrow contracts +
e-sign + `hire.completed` writing to spine. *Later:* AI matching, scheduling, call sheets.

---

## 3. RightsForge — the rights marketplace (assets + IP)

Originally planned as two separate products — **StoryForge** (IP marketplace) and **RightsHub**
(asset licensing). Merged: they're the same engine underneath (list work → buyer acquires rights →
provenance/payment matter), split only by deal shape. One product, `listing_type` of `asset` or
`ip`. This section replaces the old §3/§4 split — if you see "StoryForge" or "RightsHub" referenced
anywhere else in this repo, it means RightsForge.

**Built (real, not a mockup):** both modes live in `rightsforge/` (port 5003). Asset mode: category
tabs, tiered license options, automatic royalty splits, instant multi-buyer licensing, `asset.licensed`
loop. IP mode: format tabs, listing detail with logline + option/license/purchase terms, a 3-step
deal flow (proposed → agreed → paid), exclusivity locking once a deal completes, `ip.optioned` /
`ip.licensed` / `ip.purchased` loop. Shared login via FrameVault, verified end-to-end.

**Go grander — asset mode**
- **Royalty splits that just work.** Multi-party splits paid automatically on every sale — the thing
  that's painful everywhere else. Already built; extend to more complex split rules.
- **In-browser preview for every type.** Waveform + scrub for audio, hover-play for video/VFX, live
  LUT preview on a sample frame. Preview quality drives conversion.
- **License clarity.** Plain-English license terms + a machine-readable license record + provenance.
- **Usage-based & subscription licensing.** Not just one-off — subscriptions, per-project, enterprise
  seats.

**Go grander — IP mode**
- **Protected reading rooms.** Watermarked, access-controlled previews (view-only, per-viewer
  watermark) so writers can share without leaking. This is the #1 fear you solve.
- **Richer deal rooms.** Templated negotiation terms + real escrow, not just the 3-step flow.
- **Discovery that respects IP.** Producer-side search by genre/comparables/budget; "comps" tagging.
- **Coverage & signals.** Community/edit signals and optional professional coverage — a trust layer
  on quality without gatekeeping.
- **This gap is live right now:** Coverfly (a direct comp) shut down in August 2025 and nothing has
  replaced everything it bundled — see [SCALE.md](SCALE.md) for the sourced detail. Worth prioritizing
  IP-mode depth sooner rather than later while that gap is open.

**Steal from**
- **Artlist / Epidemic Sound** — the gold standard for music/SFX licensing UX; clean license clarity,
  great preview players. Copy the player and the "one simple license" messaging.
- **Pond5 / Envato Elements** — multi-category stock marketplaces; category browse + search facets.
- **Splice / Gumroad / Motion Array** — sample/asset preview and instant-delivery patterns.
- **The Black List** — script hosting, evaluations, and discovery. Study hard.
- **Google Docs / Scribd / DocSend** — protected, view-only, per-viewer-tracked document reading rooms.

**Roadmap** — *Now (done):* both modes, license purchase, deal flow, auto-splits, exclusivity lock.
*Next:* rich previews per asset type, protected reading rooms for IP, subscription licensing.
*Later:* enterprise seats, comps engine, coverage marketplace, provenance registry.

---

## 4. CreatorStack — competitions

**Built:** challenge cards, featured challenge with brief + prize + judging criteria, community
leaderboard, `challenge.won` loop.

**Go grander**
- **Brief → submission → judging → funding, fully structured.** Sponsors post structured briefs;
  submissions are standardised; judging is transparent (criteria weights shown); winners get *funded
  into production* — the hook that makes this more than a contest site.
- **Two-sided flywheel.** Brands get talent + concepts; creators get paid opportunities + reputation.
  Wins auto-credit FrameVault, which pulls people back in.
- **Community judging + expert panels.** Blend of votes and juried scoring, with anti-gaming.
- **Funded productions route into FilmCrew + OTT Studio.** The winning concept becomes a real
  project in the ecosystem — the cross-product magic moment.

**Steal from**
- **Talenthouse / Genero** — brand creative challenges → creator submissions (the closest analog).
- **99designs** — contest mechanics, submission galleries, client picking a winner.
- **Kaggle** — leaderboards, structured evaluation, transparent scoring for competitions.
- **Product Hunt** — daily ranking + community voting UX and social proof.
- **Cannes Lions / D&AD case-study pages** — how to present winning work aspirationally.

**Roadmap** — *Now:* post challenge, submit, vote, award. *Next:* structured judging + prize payout +
`challenge.won`. *Later:* funded-production pipeline into FilmCrew/Studio, expert panels.

---

## 5. OTT Studio — the workspace

**Built:** production board, asset tray, AI job panel (queued/running/done), shared members,
`project.published` loop.

**Go grander**
- **A real production workspace, not storage.** Tasks, shot lists, call sheets, review & approval,
  versioning — the connective tissue of a production.
- **AI orchestration as a first-class panel.** Queue mechanical jobs (transcode, sync, rough color,
  transcription, reframe) with clear provenance of what AI touched — feeding FrameVault disclosure.
- **Review & approval like Frame.io.** Frame-accurate comments, version stacks, client review links.
- **Import from RightsForge, publish to FrameVault.** The workspace is where the ecosystem's assets
  and outputs flow through — publishing stamps provenance and indexes to search.

**Steal from**
- **Frame.io** — the reference for video review/approval, versioning, and comments. Study deeply.
- **Notion / Linear** — project management, docs, and task boards (you already echo this).
- **Runway / Descript** — AI-assisted creative tooling UX (how AI actions are surfaced without
  taking over).
- **Figma** — multiplayer presence, shared cursors, comment threads (the collaboration feel).
- **Google Drive / Dropbox** — but explicitly position *against* "just storage."

**Roadmap** — *Now:* workspace + board + asset tray + AI job stubs. *Next:* review/approval +
versioning + real AI job runners. *Later:* multiplayer presence, timeline/edit concepts, deep
Frame.io-class review.

---

## 6. Global UI/UX references (the whole platform)

- **Linear** — the benchmark for a fast, keyboard-driven, dark, precise product OS. Your ⌘K, speed,
  and restraint should aim here.
- **Vercel / Raycast** — command palettes, clean dark surfaces, developer-grade polish.
- **Superhuman** — speed as a feature; keyboard-first; the "this feels fast" emotion.
- **Notion** — one app, many modules, shared primitives (your exact structural bet).
- **Arc browser** — the persistent shell + spaces mental model.
- **Stripe** — docs, dashboards, trust-through-clarity; the gold standard for a payments-adjacent
  brand.
- **Read.cv / Cosmos / Savee** — editorial, creative-native aesthetics for the profile/discovery
  surfaces.

**Design principles to hold the line on:** one shell that never reloads; ⌘K everywhere; per-product
accent hues for wayfinding but one interaction color; speed and keyboard support as identity; dark,
editorial, un-hyped voice.

---

## 7. Full build roadmap (phased)

> **Status note:** this phased plan (V0–V3) was written when the whole ecosystem was still mockups.
> It's since moved much faster than the plan assumed — see [SCALE.md](SCALE.md) §1 for what's
> actually shipped (all five products are real, working apps with the identity + credit seams wired
> and verified end-to-end). The phases below are kept as the original sequencing logic, not a live
> status tracker.

### V0 — Prototype (done ✓)
Architecture, IA, schema, API design, design system, and a clickable shared-shell prototype with all
five products. Purpose: prove the vision and the "one platform" feel.

### V1 — "The trust layer is real" (the wedge MVP)
> Sharpened around the AI-era wedge from [STRATEGY.md](STRATEGY.md): *AI made creation free; we build
> the trust layer.* V1's job is not "a functional product" — it's to make **verified identity +
> provenance** the thing CreativeOS is known for, in one real community (film), before anyone else
> owns that ground. Everything below is ordered by that wedge, not by feature completeness.

**P0 — The trust spine (the differentiator, built first).**
- **Verified identity + `/@handle` public FrameVault pages.** The land-grab surface — beautiful,
  shareable, SEO-indexed, so creators market the platform for us. Identity verification (Stripe
  Identity or similar) is the trust primitive everything hangs off.
- **Provenance receipts.** Every published/portfolio piece gets a signed provenance record — content
  hash + timestamp + contributors. This is the old Canonchain/Veridact DNA, folded in as *the*
  headline feature, not a footnote.
- **Transparent AI-disclosure.** A first-class, structured "what AI touched this, and how" record on
  every piece. Push it as something studios can *require* — trust infra others adopt.

**P1 — The spine that makes it usable.**
- One auth/session + the **event bus** (so provenance/reputation update automatically).
- Wallet + payments (Stripe Connect), notifications, unified search.
- A computed, explainable **reputation graph** (decay-aware, from real events) — trust made visible.

**P2 — The first magic moment, provenance-stamped.**
- Ship **one** end-to-end loop that proves the thesis: **FilmCrew `hire.completed` → FrameVault
  credit + provenance receipt + reputation update + wallet escrow.** The point isn't "hiring works";
  it's that a real transaction *mints verifiable, trusted history* automatically.

**Deliberately NOT in V1:** full marketplaces, the social feed/reels/courses at scale, the other four
products' depth. Those are surface area; V1 is about owning the wedge. Win "verified, provenance-
backed creative identity for film" first — breadth comes in V2/V3.

### V2 — "Two-sided products"
- **FilmCrew** and **RightsForge** fully functional (both have clear money + clear supply/demand).
- Real contracts/escrow (FilmCrew) and royalty splits + deal flow (RightsForge).
- Cross-product loops firing for real via the event bus.

### V3 — "The ecosystem compounds"
- **CreatorStack** and **OTT Studio** built out.
- The full magic-moment chain (win → funded → hired → paid → credited) works.
- AI orchestration, matching, and provenance mature.
- Public creator pages driving organic acquisition.

**Sequencing logic:** the **trust wedge** first (verified identity + provenance + AI-disclosure — the
thing that makes CreativeOS matter in the AI era) → the products with the clearest money and two-sided
demand next (FilmCrew, RightsForge) → the flywheel/creative + social/course products last (CreatorStack,
Studio, plus the feed/reels/Learn surfaces in `app/`) once there's an audience to power them. Own the
wedge before adding surface area.

---

## 8. What "full throttle" looks like (targets to design toward)

- A creator can run their **entire professional life** in CreativeOS: get discovered, get hired, get
  paid, license their work, enter competitions, produce, and publish — one login, one wallet, one
  reputation.
- Every action **compounds**: each hire, license, and win makes the creator's identity more valuable
  and the platform stickier.
- The **public creator page** is good enough that creators share it everywhere — free acquisition.
- **Trust is the product:** verification, provenance, transparent AI disclosure, and reputation are
  things *other companies rely on*, not just internal features.

---

## 9. Open questions to decide (your calls)

1. **Consumer creators or studios/brands first?** The supply side (creators) or the demand side
   (studios/brands with money)? Recommend seeding creators via FrameVault, then bringing demand.
2. **Take rate model.** Marketplace fees (FilmCrew/RightsForge) vs. subscription
   (Studio/FrameVault Pro) vs. both. Likely both — transactional + a Pro tier.
3. **How hard to lean on provenance/Veridact DNA?** Trust infrastructure could be *the* wedge, or a
   feature. Decide how central "proof of authorship" is to the pitch.
4. **Film-first or all-creative?** The prototype leans film/cinematography (your world). Decide
   whether to nail that niche first or stay broad from day one. Recommend: win film, then expand.
