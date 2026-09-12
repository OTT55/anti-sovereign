# CreativeOS

**The operating system for creative professionals.**

CreativeOS is not six startups. It's one ecosystem with six integrated products that share a
single spine — one login, one identity, one design language, one notification stream, one search,
one payments layer, one permission model.

Users should never feel like they're switching between companies. They're moving between rooms in
the same building.

---

## Why one platform instead of six

Five independent startups means five times the cost of the boring, unglamorous work: auth, billing,
trust, moderation, support, and cold-start user acquisition. None of that is a moat, and all of it
has to be rebuilt five times.

Consolidating flips the math:

- **Shared spine, built once.** Auth, profiles, notifications, search, payments, and permissions
  are infrastructure, not product. Build them once and every product inherits them.
- **Network effects instead of six cold starts.** A creator who signs up for one product already
  has an identity, a portfolio, and a reputation the moment they open the next. Each product makes
  the others more valuable.
- **One relationship with the user.** One subscription, one profile, one reputation graph — the
  switching cost compounds across the whole ecosystem.

---

## The six products

| Product | Layer | One-line purpose |
|---|---|---|
| **FrameVault** | Identity | Verified creator profiles, portfolios, reputation, AI-contribution history. The foundation. |
| **FilmCrew** | Collaboration | Hire creatives, assemble production teams, match people to projects. |
| **RightsForge** | Rights marketplace | License creative assets (music, SFX, LUTs, VFX…) instantly, or option/license/sell original IP (scripts, novels, pilots…) — one marketplace, two deal modes. Originally planned as separate products (StoryForge + RightsHub); merged because they're the same engine underneath. |
| **CreatorStack** | Competitions | Brands post challenges; winning concepts become funded productions. |
| **OTT Studio** | Workspace | Cloud production workspace — projects, AI orchestration, assets, collaboration. |
| **Story Atlas** | Story intelligence | A structured workspace for building any story's canon — characters, timeline, lore, relationships — with a consistency engine that catches contradictions. Publishing a canon credits FrameVault. |

**FrameVault is the root.** Every other product reads from and writes to it. FilmCrew hires update
FrameVault's project history; RightsForge sales update its earnings; CreatorStack wins update its
reputation. Identity is the thing every other product hangs off.

---

## AI philosophy

Design every product assuming AI gets dramatically more capable over time. That means **not** betting
the platform on features AI will commoditize (generating the script, cutting the edit, composing the
track). Instead, build around the things that get *more* valuable as generation gets cheaper:

> identity · trust · collaboration · workflow · ownership · licensing · reputation · coordination

When anyone can generate the asset, the scarce and defensible things are *who made it*, *whether you
can trust it*, *who owns it*, and *how a team coordinates around it*. AI enhances the ecosystem —
it doesn't compete with it.

---

## This repository's intent

This started as a **living product ecosystem in prototype form** — mockups and architecture before
a single line of backend. That phase is done: all six products are now real, working Flask apps,
each with its own database, verified end-to-end against a live FrameVault. `prototype/` remains as
the original clickable mockup (useful for the whole-ecosystem view at a glance); the folders next to
it are the real thing.

---

## Repository structure

```
creativeos/
  README.md                    ← you are here
  STRATEGY.md                  Positioning, the AI-era trust wedge, the pitch
  ROADMAP.md                   Per-product "go grander" ideas + the phased build plan
  SCALE.md                     How the build system scales, go-to-market, competitors (sourced)
  OTT_DESIGN_CONSTITUTION.md   The full design philosophy (copied into every product folder)
  DEPLOY.md                    How to take a product from localhost to the internet
  docs/                        The original architecture proposal (still the reference)
    architecture.md            System architecture: the shared spine + how products plug in
    information-architecture.md Navigation model, URL structure, screen inventory
    database-schema.md         Proposed schema for the shared spine + per-product tables
    api-design.md              REST/event API surface for the shared services
    design-system.md           Tokens, type, color, components — the one design language
  prototype/                   The original clickable mockup of all five products
  framevault/                  REAL — identity + provenance (port 5001)
  filmcrew/                    REAL — collaboration + hiring (port 5002)
  rightsforge/                 REAL — rights marketplace, assets + IP (port 5003)
  creatorstack/                REAL — competitions (port 5005)
  studio/                      REAL — creator workspace (port 5006)
  story-atlas/                 REAL — story canon + consistency engine (port 5109)
```

---

## Lineage

CreativeOS is the successor vision to the **Sovereign Stack** — the earlier set of standalone
proofs-of-concept in this repo (`canonchain-lite`, `arcvault-seed`, etc.). Those remain as prior
art. The core ideas carry forward and consolidate:

- Canonchain's rights registry + ArcVault's IP engine → **RightsForge** (asset licensing + IP
  marketplace, one product)
- ContextCore's workspace intelligence → **OTT Studio**
- Sovereign Edit / Canonchain identity → **FrameVault**
