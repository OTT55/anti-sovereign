# 0002 — Database and data model

**Date:** 2026-07-21
**Status:** Accepted
**Applies to:** [`schema.sql`](../schema.sql)

## Context

The MVP stored one table of registrations and rebuilt everything else on the fly.
A production registry needs to answer, safely and at scale: *who* registered
*what*, *when*, is the record *untampered*, and *prove* it belongs to the registry.
That requires a real data model and a real database.

## Decision

### Why SQLite now, PostgreSQL later (the "which database" question)

- **SQLite now.** SQLite is a database that lives in a **single file** with zero
  setup. It gives us a *real* relational database — real tables, real constraints,
  real transactions — with nothing to install. Ideal for building and proving.
- **PostgreSQL later.** Postgres is a database **server** built for many people
  writing at once, with replication and backups. It's the standard destination
  when an app grows.
- **Why the swap is cheap:** every database access goes through a few helper
  functions, and the schema deliberately avoids SQLite-only tricks. So moving to
  Postgres changes the *connection*, not the app. We chose SQLite to move fast
  without painting ourselves into a corner.
- **The honest trade-off:** SQLite allows only **one writer at a time**. Fine for
  one machine; wrong for millions. That limitation is exactly *why* Postgres is on
  the roadmap — and why we isolated database access now.

### The three tables (the "why these tables" question)

**`creators`** — the owner of a registration. A registry claim only means something
if it's tied to *someone*. We store an owner from day one even though V1 login is
stubbed (ADR on auth to follow). This is what makes Canonchain multi-user without a
future schema rewrite — the seats are already built, we just haven't turned on the
turnstile.

**`registrations`** — one row per registered work. Key columns and *why each exists*:

- `file_hash` — the SHA-256 fingerprint; **unique**, so the same file can't be
  registered twice. This column *is* the Merkle leaf.
- `creator_id` — links the work to its owner (the multi-user spine).
- `leaf_index` — the work's fixed position in the Merkle tree (its order of
  arrival). We **store** it instead of recomputing it, so a work's proof is stable
  and fast to build.
- `signature` — an **HMAC-SHA256 "wax seal"** over the record. If anyone edits a
  stored row later, the seal won't match and verification catches it. This is what
  turns a database row into a *certificate you can hand to a third party*.
- `registry_id` — a friendly public id (e.g. `CC-AB12CD34EF56`) so people cite a
  registration without exposing internal row numbers.

**`merkle_checkpoints`** — periodic **signed snapshots** of the registry's Merkle
root at a given size. Two reasons: (1) **scale** — verification can prove inclusion
against a known anchor instead of rebuilding the tree from zero every time; (2)
**trust over time** — each checkpoint is a timestamped, signed statement of "the
whole registry looked like *this* at size *N*," which is a stronger audit trail
than a single ever-changing root.

### Indexes

We add indexes on the three look-ups we actually perform — by hash (verify), by
creator (a creator's registry page), by leaf position (building proofs in order).
An index is a shortcut that keeps those look-ups fast as the table grows; we add
them only where we query, because each index has a small write cost.

## Why (summary)

The model is "small today, same shape at scale." Every column earns its place by
serving one of: *ownership* (creators, creator_id), *tamper-evidence* (signature),
*provability* (leaf_index, checkpoints), or *usability* (registry_id).

## Trade-off

- Storing `leaf_index` and `signature` is a little redundancy in exchange for
  stable proofs and tamper-evidence — a good trade for a registry.
- Checkpoints add a table we didn't strictly need at MVP size; we add it now
  because retrofitting an audit trail later is far more painful than designing it
  in.
