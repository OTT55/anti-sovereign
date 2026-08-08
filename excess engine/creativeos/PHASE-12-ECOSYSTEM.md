# Phase 12 — The Ecosystem Shell

Recorded 2026-08-03 from OTT's *Digital Ecosystem Creation Protocol*. Build
starts next week; this file exists so the engine work that has to land **first**
is known now rather than discovered halfway through.

---

## What the brief actually asks for

> *"Do not create a collection of apps. Create a unified ecosystem. The user
> should feel: I belong to this technology universe."*

Identity-first navigation, a central command centre, an AI layer that is the
operating system rather than an application, a developer ecosystem, a trust
layer, and a sense of time passing. Held to the standard of Apple HIG, Fluent,
Linear and Figma — and explicitly **not** generic SaaS dashboards, Tailwind
templates or glassmorphism.

## The honest division of labour

Most of that protocol is **design and frontend**, and this repository builds
**engines**. Writing a typography scale or an app icon here would be the exact
category error the whole side-quest exists to avoid, and I am scope-locked to
`excess engine/` regardless.

But the brief is not *only* design. Six of its demands are capability
questions, and a beautiful shell over an engine that cannot answer them is a
mockup. Those are Phase 12's job:

| The brief asks for | Engine capability needed | Status |
|---|---|---|
| Universal command palette, intelligent search | search across **every** space and application | **missing** — `index_for(space_id)`, one index per space |
| Ecosystem home: recent activity, what changed, what matters | a cross-application feed and digest | **missing** — `brief()` exists but is per-space |
| Teams, organisations, "what you can access" | accounts, orgs, roles, permissions | **exists** — `platform/engine.py` |
| Collaboration and sharing | invite → pending → accept/decline | **partial** — `invite` is a permission string; `add_member()` adds immediately, with no pending state. Both FilmCrew and OTT Studio already implement the real flow in their apps |
| Trust layer: privacy centre, permissions, transparency | who saw what, who changed what, and why | **partial** — the graph is bitemporal and every assertion is sourced, so the data exists; nothing surfaces it as an access record |
| Time-based evolution: daily summaries, memories, history | the Memory Engine | **named but not built** — the constitution lists it; there is no `memory/` module. The bitemporal graph (`history_of`, `retract`, `as_of`) covers most of what it describes, so this is a consolidation question, not a rewrite |

Two more the brief implies rather than states:

- **Notifications** exist (`platform.notify`) but nothing aggregates them into
  the "what happened while you were away" the home screen needs.
- **Files** exist (`storage.put/get`, content-hashed, with `duplicates()`), which
  is what every application's upload path actually wants.

## The order that makes sense

1. **Cross-space search.** Everything else in the ecosystem shell — command
   palette, intelligent search, the home screen's "connected applications" —
   reduces to this one capability. Nothing else is worth starting first.
2. **A digest**: what changed, across every space, since a point in time. This
   is what makes "daily summaries" and "memories" possible, and it is the
   Memory Engine question in a concrete form.
3. **Invitations** as a real state machine — offered, accepted, declined,
   expired — rather than immediate membership. Two applications already need
   it and have each written their own.
4. **An access record**: who read what, when. The trust layer cannot be built
   from data that was never recorded.

Only then does a shell have anything real to render.

## What this phase must not become

The brief says *"do not stop at concepts, implement layouts, components,
navigation, animations"* — and that is correct for the applications. It is
**wrong for this repository**, which has no UI and should not grow one. The
deliverable here is the capability the shell calls into. If the two get mixed,
the engines stop being importable and become a website.

## Prerequisites still open

Phase 12 is not next. Before it:

- **OTT Studio engine** — the last of the six CreativeOS applications.
- **Canonchain** — the only remaining standalone company, and the one flagged
  as having a copy-pasted evaluation doc that likely describes work nobody did.

Both are in flight under OTT's standing rule: *build everything first, improve
later.*
