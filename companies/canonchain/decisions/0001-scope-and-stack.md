# 0001 — Canonchain is the first production app; scope & stack

**Date:** 2026-07-21
**Status:** Accepted

## Context

The Sovereign Stack has MVPs for all its main companies. The founder decided to
promote **one** to a real, production-grade application first. The CreativeOS
track (FrameVault, etc.) and Cinematic AI are handled separately and are out of
scope for this work.

## Decision

1. **Canonchain is the first production app.** It's the rights registry — the
   foundation other companies (Veridact, Sovereign Edit) build on, it works fully
   offline with real cryptography (no paid API, no credit blocker), and it's the
   clearest expression of the Stack's thesis: *verified origin is the only scarce
   asset.*
2. **We build in place**, evolving `companies/canonchain/`. The MVP is preserved
   in git history (commit `44b739d`), so nothing is lost.
3. **Stack:** Python + Flask, SQLite now (PostgreSQL later), hand-written
   HTML/CSS/JS. Rationale in the trade-offs below and in ADRs 0002–0003.

## Why

- **Foundational beats flashy for a first build.** Shipping the registry gives the
  other trust-layer products something real to plug into. Building a leaf before
  the root is motion without progress.
- **No external dependencies = it always runs.** Canonchain needs no third-party
  API, so a demo can never fail because of billing or a rate limit. For a piece
  meant to be shown to universities, "it always runs" is worth a lot.
- **Reuse the stack we already know.** The whole repo is Flask + SQLite. Using it
  again means zero learning tax and code the founder can read — and it is genuinely
  production-capable, not a toy.

## Trade-off

- **Python isn't the fastest language.** For a registry, the bottleneck is the
  database and network, not Python — so this is the right call until profiling ever
  says otherwise. Swapping later is possible because the app is structured behind
  clean seams (see the app-structure ADR).
- **SQLite has one writer at a time.** Perfect for building and proving; wrong for
  millions of simultaneous users. That's *why* the PostgreSQL swap is planned and
  isolated (ADR 0002) — the design makes the upgrade cheap, not a rewrite.
- **Building in place** means the tidy MVP grows into a bigger codebase. Acceptable:
  git preserves the MVP, and a real app needs real structure.
