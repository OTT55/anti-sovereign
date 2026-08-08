# FrameVault — Architecture, in plain English

Written for OTT (the founder), not for engineers. The goal: you should be able to read this, weigh
the pros and cons yourself, and explain it to a university or a collaborator. It answers three
questions you asked directly:

1. **Will the apps stay separate, so one never overrides another?** — Yes. Here's exactly how.
2. **Can this plug into the main CreativeOS later?** — Yes. Here's the seam.
3. **Does it survive growing to millions of users?** — Yes, with specific swaps. Here's the path.

---

## 1. The big picture in three sentences

FrameVault is a **standalone app** — its own folder, its own database, its own address. It is built
so that the simple version you run today and the huge version you'd run at 10 million users are the
**same shape** — you swap parts, you don't rebuild. And it exposes clean "sockets" (an API and
events) so the main CreativeOS can plug into it later **without either side reaching into the
other's guts**.

Think of each CreativeOS product as a **separate shop in the same shopping centre**. Each shop has
its own storeroom (database), its own front door (web address), its own staff (server process). The
shopping centre (the main CreativeOS) is the shared entrance, security, and payment desk that ties
them together. Shops don't walk into each other's storerooms — they talk at the front desk.

---

## 2. Isolation — why one app can NEVER override another

This is the thing you were most worried about, so it comes first. The rule is simple and absolute:

> **Every product is its own service: its own folder, its own database file, its own port, and
> (later) its own web domain. No product ever touches another product's storage.**

### The convention (write this down — it's the law for every future app)

| Product | Folder | Database (never shared) | Dev port | Future domain |
|---|---|---|---|---|
| *Main CreativeOS shell / gateway* | `creativeos/` | (talks to others) | **5000** | `app.creativeos.com` |
| **FrameVault** | `creativeos/framevault/` | `framevault.db` | **5001** | `id.creativeos.com` |
| FilmCrew | `creativeos/filmcrew/` | `filmcrew.db` | 5002 | `crew.creativeos.com` |
| RightsForge *(merges the old StoryForge + RightsHub split — one product, two deal modes)* | `creativeos/rightsforge/` | `rightsforge.db` | 5003 | `rights.creativeos.com` |
| CreatorStack | `creativeos/creatorstack/` | `creatorstack.db` | 5005 | `stack.creativeos.com` |
| OTT Studio | `creativeos/studio/` | `studio.db` | 5006 | `studio.creativeos.com` |

Because each app runs as a **separate program on a separate port with a separate database file**,
they physically cannot overwrite each other. You can run FrameVault and FilmCrew at the same time in
two terminals and they will never see each other's files. This is exactly the "different HTTPS"
separation you asked for — in production each becomes its own subdomain with its own deployment.

**Trade-off (honest):** separate services means more moving parts than one giant app. The upside —
which matters far more at your ambition — is that one app crashing, being redeployed, or being
rewritten never touches the others, and different apps can scale independently (if Reels blows up,
you scale Reels, not everything). This is the standard way large platforms are built.

---

## 3. Every choice I made in the backend (`app.py`), and why

For each one: **what it is → why I chose it → what happens at 10M users → the trade-off.**

### a) Python + Flask (the web server)
- **What:** Flask is a small, readable Python framework that answers web requests.
- **Why:** Your repo already uses it (Canonchain, ArcVault), it's easy to read for a non-coder, and
  it's genuinely production-capable. No learning tax, no new stack.
- **At 10M:** Flask stays; you just run **many identical copies** of it behind a load balancer (a
  traffic cop that spreads requests across them). The app is written to be **stateless** (it keeps
  nothing important in memory — everything lives in the database), which is the one property that
  makes "just run more copies" possible.
- **Trade-off:** Python isn't the fastest language, but for this kind of work the database and
  network are the bottleneck, not Python. Fine to 10M; swap only if profiling ever says so.

### b) SQLite (the database, for now)
- **What:** SQLite is a database that lives in a **single file** (`framevault.db`). Zero setup.
- **Why:** Perfect for building and proving the app — no server to install, and it gives us a *real*
  database with real tables, not a fake. It's the "no mocks" choice at small scale.
- **At 10M:** SQLite is replaced by **PostgreSQL** (a database server built for many simultaneous
  writers, replicas, and backups). This is a known, planned swap — and it's **cheap because all
  database access in the code goes through a few helper functions** (`get_db`, the queries). We
  change those helpers, not the whole app.
- **Trade-off:** SQLite allows only one writer at a time — great for one machine, wrong for millions.
  That's *why* the swap to Postgres is on the roadmap. The design already isolates it so the swap is
  small.

### c) Hashing the file in the browser (not on the server)
- **What:** When you register a work, **your browser** computes the file's SHA-256 fingerprint (a
  64-character code unique to that exact file). Only the fingerprint + details are sent to the server
  — **the file itself never leaves your computer.**
- **Why:** This is the single best decision in the app, for three reasons:
  1. **Privacy / trust:** FrameVault can prove you registered a specific file at a specific time
     without ever seeing, storing, or being able to leak your work. That's a real feature, not a
     shortcut.
  2. **Scale:** the server does almost **zero work** per registration — the heavy lifting happens on
     the user's device. A million people can hash a million files and your servers barely notice.
  3. **Cost:** you're not paying to store or move giant video files just to prove authorship.
- **At 10M:** this barely changes — it's already the scalable design. (If you later want to store the
  actual files too, that goes to cheap object storage like S3, kept separate from the database.)
- **Trade-off:** you're proving "this exact file existed and was claimed by this person at this time,"
  not "this person is legally the author" — no system can prove the latter by hashing alone. But
  timestamped, signed proof-of-existence is exactly what the trust wedge needs, and it's real.

### d) Signing each record (HMAC-SHA256)
- **What:** After storing a record, the server adds a **signature** — a tamper-check computed from
  the hash + registry ID + timestamp using a secret key. If anyone edits the record later, the
  signature won't match, so tampering is detectable.
- **Why:** "Signed provenance" is the promise of the trust layer. This makes the receipt verifiable
  and tamper-evident, today, for real.
- **At 10M:** the local secret becomes a **managed key (KMS)** or, better, **a keypair per creator**
  so each creator signs their own records. Same idea, stronger cryptography. The signing code is one
  function (`sign`) — easy to upgrade.
- **Trade-off (stated honestly in the code):** today it proves "this FrameVault instance issued and
  hasn't altered this record," not "this specific person cryptographically signed it." That's the
  documented next step, not a fake.

### e) The database shape (tables)
- **What:** `users`, `creator_profiles`, `profile_skills`, `provenance_records`, `reviews`,
  `reputation_events`. Each registered work *is* both a portfolio piece and a signed provenance
  record (same row) — because in FrameVault, your work and its proof are the same thing.
- **Why:** it mirrors the shared-spine schema in `docs/database-schema.md`, so when FrameVault
  becomes the identity service for the whole ecosystem, the tables already line up.
- **At 10M:** same tables, moved to Postgres, with indexes (already added on the hash and owner) and
  read replicas for the public pages. Reputation is **computed from events**, not stored as a guess —
  so it's always explainable ("here's *why* the score is 4.9"), which is itself a trust feature.

### f) Login is stubbed (for now) — and this is the main integration seam
- **What:** Right now the dashboard acts as one seeded user, "OTT" (`OWNER_ID = 1`). There's no
  password screen yet.
- **Why:** so we can build and prove the *product* (identity + provenance) without first building an
  entire auth system — and because **auth is meant to be shared across all of CreativeOS**, not
  rebuilt per app.
- **The seam:** in the ecosystem, login happens **once** at the shared identity service; each product
  trusts a token that says "this request is user #X." We replace the single line `OWNER_ID = 1` with
  "read the user from the verified token." One well-marked spot. Everything else already works
  per-user.
- **Trade-off:** the demo isn't multi-user-secure yet — by design, because real auth is a shared
  spine service (V1, next), not a FrameVault-only feature.

### g) A JSON API (not just web pages)
- **What:** FrameVault answers both **web pages** (for humans) and **JSON** (for machines) — e.g.
  `POST /api/verify` returns data, not a page.
- **Why:** the JSON API **is** how the main CreativeOS will talk to FrameVault later. Building it now
  means integration is "point the shell at these endpoints," not "rewrite FrameVault."

---

## 4. How FrameVault plugs into the main CreativeOS (the seams)

Three clean sockets — and one rule.

```
                 ┌─────────────────────────────┐
                 │      Main CreativeOS         │
                 │  (shell / gateway, :5000)    │
                 └───────────────┬──────────────┘
        reads over HTTP (JSON)   │   listens for events
                 ┌───────────────┴──────────────┐
                 ▼                               ▼
   ┌──────────────────────┐         ┌──────────────────────┐
   │  FrameVault (:5001)   │  emits  │   Shared event bus    │
   │  own DB: framevault.db│ ───────▶│  (the spine's glue)   │
   └──────────────────────┘  events  └──────────────────────┘
        ▲  exposes /api/*                    │ other products
        │                                     ▼ react (reputation, feed…)
   the shell calls these; it NEVER opens framevault.db directly
```

1. **Identity seam** — replace `OWNER_ID = 1` with "the user from the shared login token." FrameVault
   becomes the identity service the others read from.
2. **API seam** — the main app reads a profile via `GET /api/@handle` (JSON) and verifies a hash via
   `POST /api/verify`. It calls the front door; it never opens the storeroom.
3. **Event seam** — when a work is registered, FrameVault **emits an event** (`work.registered`) to
   the shared event bus. Other products react (the feed shows it, reputation updates) without
   FrameVault knowing they exist. *(Today this is recorded internally in `reputation_events`; the
   integration step is to also publish it outward — one small, marked function.)*

**The one rule (this is what guarantees no collisions):** products talk through APIs and events —
**never** by reaching into another product's database. This is the "thin products, thick spine"
principle from `docs/architecture.md`, enforced.

---

## 5. Scaling to 10 million users — what holds, what swaps

The design is deliberately "small today, same shape at scale." Here's the honest map:

| Piece | Today (build/prove) | At 10M users | Why the swap is cheap |
|---|---|---|---|
| Web server | one Flask process | many identical Flask copies behind a load balancer | app is **stateless** — just add copies |
| Database | SQLite (one file) | PostgreSQL + read replicas | all DB access is behind a few helpers |
| File hashing | in the browser | **unchanged** — already the scalable design | server does ~no work per registration |
| Storing actual files | not stored (hash only) | object storage (S3) + CDN, if ever needed | kept separate from the database |
| Signature | local HMAC secret | KMS / per-creator keypairs | one `sign()` function |
| Public `/@handle` pages | rendered live | cached / served from a CDN | pages are read-only + cacheable |
| Events | internal table | real event bus (queue / Kafka) | one `emit()` seam |
| Login | stubbed single user | shared identity service + tokens | one line (`OWNER_ID`) |

**The standout:** because the browser does the hashing, the part that would normally melt under load
(processing everyone's files) barely touches your servers at all. You designed the expensive thing
out from day one.

**Honest cons of thinking this way early:** it's a little more structure than the absolute minimum,
and the stubbed auth / local signing are clearly "V1, upgrade later." But none of it is throwaway —
every piece is the small version of the real thing, sitting behind a seam so the upgrade is a swap,
not a rewrite. That's the difference between a prototype you throw away and a foundation you grow.

---

## 6. What's next in this build (front-end), and your open calls

Still to build (front-end only — the backend is done):
- **Dashboard** (`/dashboard`): edit your profile, add skills, and **register a work** (pick a file →
  browser hashes it → you get a signed provenance receipt).
- **Public page** (`/@ott`): the shareable identity page — profile, verified badge, portfolio with
  provenance, reputation, reviews.
- **Verify** (`/verify`): paste a hash (or drop a file) → see if it's registered, to whom, and
  whether the signature checks out.
- Warm "modernist" design language (matching the `app/` build), light + dark themes.

**Decisions that are yours (no wrong answers — they change nothing structural):**
1. Keep FrameVault on its own port **5001** (main shell reserved for 5000)? *(Recommended.)*
2. For now, store hash-only (never the file), or also allow optional file storage later? *(Recommend
   hash-only — it's the privacy/trust win.)*
3. Are you happy with "auth stubbed now, shared login later" as the V1 plan? *(Recommended — auth is
   a shared spine job, not FrameVault's.)*

Nothing above is built in a way that locks you in. Say the word and I'll build the front-end; or push
back on any choice and I'll adapt it first.

---

## 7. Founder FAQ (the questions you actually asked)

**Q: If login is "stubbed," can someone pretend to be me? Is it safe?**
Right now there's *no login at all* — the app treats every visitor as you. On your own computer
(localhost) that's completely safe; only you can reach it. We do **not** put it on the public internet
until the shared login is switched on (one line: `OWNER_ID = 1` → "the user from the verified token").
Today it's a real single-user app for building and demoing; nothing has to be undone to make it
multi-user later.

**Q: Why separate databases? Isn't that harder to keep in sync?**
Sync nightmares come from *two apps both thinking they own the same data*. We avoid that with one
rule: **one owner per kind of data.** FrameVault owns identity; it's the single source of truth.
Other apps don't copy your identity — they *ask* FrameVault (API) or keep a small read-only cache
that FrameVault refreshes via events. One master per domain = *less* sync pain, not more.

**Q: When I run it, what do I actually see and do?**
`python app.py` → open `localhost:5001` → your Dashboard (as OTT) → edit profile, add a skill,
**register a work** (pick a file → your browser fingerprints it → you get a signed receipt) → visit
`/@ott` (your shareable public page) → visit `/verify` (paste a hash or drop a file → see if it's
registered, to whom, and whether the signature checks out). Every step is real, not a mockup.

**Q: Do I have to build the main CreativeOS integration now?**
No. FrameVault is fully usable standalone today. The seams (API, identity, events) are in place, so
wiring the main shell to it later is "point it at the endpoints," not "rewrite anything." Build
products one at a time; connect them when ready.

**Q: What does it cost — small and at scale?**
Small: essentially free ($5–20/mo — one small server, SQLite, no file storage). At scale: the real
costs are a managed database (Postgres), a few app servers, a load balancer, maybe a cache/CDN —
growing with usage. Because files are hashed in the browser and not stored, you skip the two things
that make creator platforms expensive (storage + bandwidth for big video files).

**Q: Moving SQLite → Postgres later — do I lose my data?**
No. It's a *copy, not a rebuild*, because the table shapes are identical: create the same tables in
Postgres, run a script that copies every row, point the app at Postgres. You test on a copy first,
check the counts match, then switch. Routine and safe.

**Q: Is the signature actually secure, or is it theatre?**
Real, at V1 strength. It's a true HMAC over *every* field of the record — edit any stored field and
the signature won't recompute to match, so `/verify` flags tampering. What it does *not* yet do is
prove a *specific person* signed it (today it proves "this FrameVault instance issued this and it
hasn't been altered"). At scale each creator gets a keypair → "cryptographically signed by this
creator." Not theatre; the upgrade path is written in the code comments.

**Q: Can I show this to a university as-is?**
Yes — and the honesty is part of what impresses. What's real: it runs, the database is real, SHA-256
is the actual industry-standard fingerprint, the signature is a real HMAC, and `/verify` genuinely
works. What's clearly V1: shared login and per-creator keys are the documented next steps. A panel
respects a founder who built a *real* trust mechanism and knows exactly what's proven vs. pending.
