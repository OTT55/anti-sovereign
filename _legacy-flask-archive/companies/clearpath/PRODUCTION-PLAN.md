# Clearpath — Production Build Plan (plain English)

Written for OTT (founder / CEO / CTO). You should be able to read this, weigh
each call yourself, and explain it to a university or investor. No jargon
without a plain-English translation beside it.

This is the plan to take Clearpath from the **MVP** (already built) to a real
production-grade application — the fourth in the Sovereign Stack, after
Canonchain, Veridact, and Sovereign Edit.

---

## 1. What Clearpath is, in one breath

Clearpath looks at a proposed cross-border transfer — money, a security, a
media file, a dataset — and tells you **ALLOW**, **REVIEW**, or **BLOCK**,
showing exactly which rule fired, its legal basis, and what would fix it.
Every decision is written to a log nobody can quietly edit afterward. It's
the *compliance pillar*: the one piece of the Stack that answers "are we
allowed to do this, and can we prove we checked?"

---

## 2. The core idea — and why we do it this way (READ THIS)

There are two ways to build a compliance API. Only one is defensible long-term.

1. **❌ Rules alone.** Any competitor can write "if destination is sanctioned,
   block." Compliance rules are public law — a law firm will hand them to you
   for free. A rules engine with no other advantage is a commodity, and it
   will be priced like one.

2. **✅ Rules over *attested* facts, not self-reported ones.** Every other
   compliance product in this space evaluates facts a customer typed into a
   form — "is this PII? is provenance attached?" — and takes their word for
   it. Clearpath sits inside a stack that can *prove* some of those facts
   instead of asking: Canonchain proves who registered a file first, Veridact
   proves a video is a real capture, Sovereign Edit proves which file is the
   approved master. "Our compliance decisions are computed from cryptographic
   evidence, not self-declaration" is the one sentence in this pitch a
   competitor can't copy in a quarter — see
   `research/14-business-moats-by-company.md`.

**Why now, specifically:** the EU AI Act's Article 50 transparency
obligations apply from **2 August 2026**. From that date, failing to disclose
AI-generated content isn't just bad practice — it's a violation with a fine
up to €15M or 3% of worldwide turnover attached. That converts "prove you
disclosed it" from a nice-to-have into paperwork every affected company now
legally needs, on a clock that's already running.

---

## 3. What Phase 1 honestly builds (done now), and its honest limit

**What's built:** the six MVP rules are no longer Python functions — they're
versioned JSON data (`rulepacks/core.json`), evaluated by a small,
hand-written condition interpreter (`app/conditions.py`). Reference data
(sanctioned countries, GDPR-adequate destinations) is versioned data too
(`refdata/jurisdictions.json`), not a Python literal. Every decision now
records *exactly* which version of the rules decided it, frozen verbatim in
the database — so a decision made today can be reproduced, unchanged, even
after the rules move on. The three disclosure questions (PII? verified
counterparty? provenance attached?) are now **tri-state** — Yes / No /
Unknown — and leaving one on Unknown produces an honest fourth outcome,
**NEEDS INFO**, when (and only when) that specific unknown actually changes
the answer, instead of silently guessing "No." Full reasoning in
`decisions/0001`–`0004`.

**The honest limit:** this phase is still entirely self-contained. The
provenance rule's "is there a provenance attestation?" question is still
whatever the caller *claims* — Clearpath doesn't yet call Canonchain or
Veridact to check. Phase 1 makes the engine trustworthy and reproducible; it
does not yet make the facts it judges independently verified. That's Phase 2.

---

## 4. What's different from the Clearpath MVP

| | MVP | Phase 1 (now) |
|---|---|---|
| Rules | 6 Python functions in `app.py` | Versioned JSON (`rulepacks/core.json`) |
| Reference data | Python literals (`SANCTIONED = {...}`) | Versioned JSON (`refdata/jurisdictions.json`) |
| Disclosure facts | Boolean; omitted = silently "No" | Tri-state; omitted = honestly "Unknown" |
| Missing information | Never surfaced — falls through to whatever "No" implies | New outcome: **INSUFFICIENT_FACTS** ("NEEDS INFO") |
| Audit entry | Records the decision | Records the decision **and** the exact frozen ruleset that made it |
| Provenance check | Caller-supplied boolean, unverified | Same, honestly labeled as unverified (Phase 2 fixes this) |

Two endpoints the MVP's own templates already called
(`/api/audit/latest`, `/api/audit/search` — the live-updating audit page and
the Ctrl/Cmd+K search) were never implemented in `app.py`; they silently
404'd. Both are real now.

---

## 5. The build, in phases

- **Phase 1 — Foundation (done this session).** Rules and reference data as
  versioned, reproducible data. Tri-state facts and INSUFFICIENT_FACTS. Same
  app-factory structure as Canonchain/Veridact/Sovereign Edit. Fully offline.
- **Phase 2 — The first real cross-company integration.** Replace the
  caller-supplied `provenance_attached` boolean with an actual HTTP call to
  Canonchain (`GET /api/verify?hash=...`, the same pattern FilmCrew already
  uses to call FrameVault). If Canonchain can't be reached, the fact becomes
  genuinely unknown — `INSUFFICIENT_FACTS`, never a guessed "No attached."
  This is the moment the moat in section 2 stops being a slide and starts
  being code.
- **Phase 3 — Rule packs as the unit of scale.** A second rule pack,
  `eu/ai-act-art50`, encoding the Article 50 disclosure obligation as data,
  loadable alongside `core` the same way. Later: a real admin surface for
  editing rules without a JSON pull request, golden-case regression tests so
  a rule-pack update can show *which past decisions would flip* before it
  ships, and sourcing `refdata` from an actual sanctions/adequacy feed
  instead of a hand-maintained file.

Each phase ends with a working app and a git commit.

---

## 6. Decisions that are yours

1. **Phase 2 timing** — wire the real Canonchain call next, or pause here and
   let Phase 1 run for a while first? *(No wrong answer — Phase 1 is a
   complete, working app on its own.)*
2. **Phase 3's first new rule pack** — Article 50 (transparency/disclosure)
   is the obvious next one given the deadline, but confirm that's still the
   priority over a tax or labor pack before real research time goes into it.

Nothing here locks us in. Push back on any of it and I'll adapt before
building.
