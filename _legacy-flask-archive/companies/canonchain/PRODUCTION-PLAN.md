# Canonchain — Production Build Plan (plain English)

Written for OTT (founder / CEO / CTO). You should be able to read this, weigh each
call yourself, and explain it to a university or investor. No jargon without a
plain-English translation next to it.

This is the plan to take Canonchain from the **MVP** (already built and working)
to a **real production-grade application** — the first one in the Sovereign Stack.

---

## 1. What Canonchain is, in one breath

Canonchain is a **rights registry**. It answers one question that only gets more
valuable as AI floods the world with copies: **"who registered this exact file
first, and when?"** — and it answers it *without you having to trust us*, because
the proof is mathematical, not our word.

That thesis is the whole Sovereign Stack in miniature: *verified origin is the
only scarce asset.* Canonchain is that sentence turned into software.

---

## 2. What already works (the MVP we're building ON, not throwing away)

The MVP is real, not a mock. It already does:

- **Browser-side hashing** — your file is fingerprinted (SHA-256) *in your
  browser*. The file never uploads. We only ever see the 64-character fingerprint.
- **Register** — we store the fingerprint, who claimed it, and the UTC time.
- **Merkle proof** — every registration gets a mathematical receipt proving it's
  part of the registry, checkable by anyone without trusting our server.
- **Verify** — paste a fingerprint, see if/when/by whom it was registered.

We keep all of this. Production is about making it **trustworthy at scale, safe,
and real-company-grade** — not about redoing the core idea.

---

## 3. What "production-grade, not MVP" actually adds

Here's the honest gap between "it works on my laptop" and "it's a real product,"
and what we'll build to close it. Each item says **what**, **why**, and the
**trade-off** — and each gets its own decision record in `decisions/`.

| # | Upgrade | Plain-English why |
|---|---------|-------------------|
| A | **Real app structure** (not one big file) | One 300-line file is fine for a demo; a real app splits into parts (database, registry logic, web routes, config) so it's testable, readable, and safe to change. |
| B | **Creator accounts, done right** | A registry claim is only meaningful if it's tied to *someone*. We make every registration owned by a creator from day one. (Login itself is stubbed for V1 — see decision 0002 — but the data is multi-user from the start.) |
| C | **Signed certificates** | Each registration gets a tamper-evident signature (like a wax seal). Edit the record later and the seal breaks. This makes a Canonchain certificate something you can hand to a third party. |
| D | **Merkle tree that scales** | The MVP rebuilds the whole proof-tree on every request. That's fine for 100 works, not for 10 million. We make it grow incrementally and checkpoint it. |
| E | **A real API** | Machines (other Sovereign Stack companies, partners) talk to Canonchain over a clean JSON API — the same seam that lets Veridact and Sovereign Edit build on top of it. |
| F | **Tests** | Automated checks that prove register/verify/tamper still work after every change. This is the difference between "I hope it works" and "I know it works." |
| G | **Config + safety** | Secrets come from the environment (never hard-coded), input is validated, errors are handled. Standard for anything on the public internet. |
| H | **The scaling path, documented** | SQLite → PostgreSQL, one server → many behind a load balancer. Written down so the upgrade is a *swap*, not a rewrite. |

---

## 4. The build, in phases (so progress is visible and reversible)

- **Phase 1 — Foundation.** Restructure into a real app; production database schema
  (creators + registrations + signed certs + Merkle checkpoints); config. Register
  + verify keep working the whole time. *(Decisions 0001–0003.)*
- **Phase 2 — Trust.** Signed certificates; incremental/checkpointed Merkle tree;
  a hardened public `/verify`. *(Decisions 0004–0005.)*
- **Phase 3 — Product.** Creator dashboard, a public registry page, a clean web UI.
- **Phase 4 — Proof.** Test suite; run it end-to-end for real; write the "how we'd
  scale to millions" doc with the exact swaps.

Each phase ends with a working app and a git commit, so we can always stop, show
it, or roll back.

---

## 5. The one decision that's yours right now

**Login / accounts for V1.** My recommendation (matching how the CreativeOS track
handled it): **build the data so every registration has an owner from day one, but
stub the actual login for V1** — the app operates as a seeded creator while we
build the product, and real sign-in is a later, well-marked step. This lets us
build the *registry* (the hard, valuable part) without first building an entire
password/identity system.

You can overrule this. But nothing about it locks us in — it's one clearly-marked
spot in the code that we swap when real login arrives.

---

## 6. Where this lives

We build **in place**, in `companies/canonchain/`. The MVP is preserved in git
history (commit `44b739d`), so we lose nothing. The folder simply grows up into a
real app.
