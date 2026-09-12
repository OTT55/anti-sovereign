# CreativeOS — System Architecture

The whole design rests on one idea: **the products are thin; the spine is thick.** Anything that
looks like infrastructure lives in the shared core and is built once. Each product is a relatively
thin experience layer on top of shared services.

---

## 1. The layered model

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            CLIENT (one app shell)                         │
│   One nav · one command palette · one notification tray · one search      │
│                                                                           │
│  FrameVault  FilmCrew  RightsForge   CreatorStack  OTT Studio              │
│  (identity)  (collab)  (rights mkt)  (contests)    (workspace)             │
└───────────────────────────────┬───────────────────────────────────────────┘
                                │  one API gateway (authn/z, rate limit)
┌───────────────────────────────┴───────────────────────────────────────────┐
│                          SHARED SPINE (services)                          │
│                                                                           │
│  Identity &     Notifications   Search        Payments &    Permissions   │
│  Profiles       (fan-out)       (unified      Wallet        (RBAC + ABAC) │
│  (FrameVault    ▲               index)        (Stripe       ▲             │
│   is its UI)    │                             Connect)      │             │
│      ▲          │                   ▲             ▲          │             │
│      │          │                   │             │          │             │
│  Messaging   Media/Asset       Reputation &   Activity /   Audit &        │
│  (threads,   Storage (CDN,     Reviews        Event Bus    Provenance      │
│   real-time)  transcode)                      (the glue)   (content auth)  │
└───────────────────────────────┬───────────────────────────────────────────┘
                                │
┌───────────────────────────────┴───────────────────────────────────────────┐
│  DATA:  Postgres (source of truth) · Redis (cache/queues) ·               │
│         OpenSearch (search) · Object storage (media) · Event log           │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 2. The shared spine — services built once

| Service | Owns | Every product uses it for… |
|---|---|---|
| **Identity & Profiles** | Users, creator profiles, verification, skills, availability | Knowing *who* the actor is. FrameVault is simply this service's front-end. |
| **Permissions** | Roles, capabilities, resource-level grants | Deciding *what* an actor may do — RBAC for coarse roles, ABAC for per-resource sharing. |
| **Payments & Wallet** | Balances, payouts, subscriptions, escrow | FilmCrew contracts, RightsForge royalties + licenses, CreatorStack prizes. |
| **Notifications** | Preferences, delivery, fan-out | One tray across all products; email/push/in-app from one source. |
| **Search** | Unified index across people, projects, IP, assets | One search box that spans every product. |
| **Messaging** | Threads, real-time delivery, read state | FilmCrew DMs, negotiation threads, workspace comments. |
| **Media/Asset Storage** | Upload, transcode, CDN, previews | Portfolios, IP files, licensable assets, workspace files. |
| **Reputation & Reviews** | Ratings, review integrity, reputation graph | Trust signals on every profile and listing. |
| **Activity / Event Bus** | The event log that connects everything | The glue — see §3. |
| **Audit & Provenance** | Immutable trail, content authentication | Ownership disputes, AI-contribution history, trust. |

**Design rule:** a product may never re-implement a spine capability. If FilmCrew needs payments,
it calls the Payments service. This is what keeps six products feeling like one platform.

---

## 3. The event bus is the glue

The reason CreativeOS feels like *one* platform is that products don't call each other directly —
they publish events, and the spine reacts. This keeps products decoupled and makes cross-product
magic (the whole point) fall out naturally.

**Example: a completed hire.**

```
FilmCrew: contract marked "delivered & paid"
        │
        └──▶ emits  hire.completed { creatorId, projectId, role, rating }
                     │
        ┌────────────┼───────────────┬────────────────────┐
        ▼            ▼                ▼                    ▼
  FrameVault    Reputation        Payments            Notifications
  appends to    updates the       releases escrow     tells the creator
  project       creator's         to wallet           + updates the tray
  history       score
```

One product acted. Four spine services reacted. FrameVault got richer without FilmCrew knowing
FrameVault exists. That decoupling is the architecture.

**Canonical cross-product events:**

- `hire.completed` → FrameVault history, Reputation, Payments, Notifications
- `asset.licensed` (RightsForge, asset mode) → Payments (royalty split), Provenance, FrameVault earnings
- `ip.optioned` / `ip.licensed` / `ip.purchased` (RightsForge, IP mode) → Payments (escrow), Notifications, FrameVault history
- `challenge.won` (CreatorStack) → Reputation, FrameVault history, Payments (prize/funding)
- `project.published` (OTT Studio) → Search index, FrameVault portfolio, Provenance
- `canon.published` (Story Atlas) → FrameVault portfolio, Reputation

---

## 4. How a request flows

1. **Client** (any product screen) calls the **API gateway** with the user's session token.
2. Gateway authenticates, checks coarse **permissions**, applies rate limits, routes to the service.
3. Service does the work against **Postgres** (source of truth), reads/writes cache in **Redis**.
4. On any state change worth reacting to, the service **publishes an event** to the bus.
5. Subscribers (Search, Notifications, Reputation, FrameVault, Provenance) update asynchronously.
6. **Search** and **Notifications** keep their own read-optimized stores in sync from the event log.

Writes are synchronous and authoritative; cross-product side effects are asynchronous and eventual.
That split is what lets the platform scale without every product blocking on every other.

---

## 5. Technology proposal (prototype → scale)

| Concern | Prototype choice | Scale path |
|---|---|---|
| Client | One SPA shell (React) hosting product modules | Module federation / per-product bundles |
| API | REST + JSON over a single gateway | Add GraphQL BFF if client needs demand it |
| Source of truth | Postgres, one DB, schema-per-domain | Read replicas → per-service DBs where hot |
| Cache / queues | Redis | Redis + managed queue (SQS/PubSub) |
| Search | OpenSearch / Meilisearch | Managed search cluster |
| Media | Object storage + CDN | + transcode pipeline, signed URLs |
| Events | Postgres `outbox` table polled → bus | Kafka / managed event streaming |
| Payments | Stripe Connect (marketplace + payouts) | + escrow ledger service |
| Auth | Session + OAuth social; one identity | + SSO/enterprise, passkeys |

This is a proposal, not a commitment. The point of the prototype phase is to validate the *shape*
(thin products, thick shared spine, event-driven glue) before hardening any single choice.

---

## 6. Why this is future-proof against better AI

The architecture deliberately puts the durable things in the spine — identity, permissions,
payments, reputation, provenance, coordination. Those are the capabilities that get *more* valuable
as AI generation gets cheaper and more abundant. AI features live inside products (OTT Studio's
orchestration, RightsForge discovery, search ranking) where they can be swapped and upgraded without
touching the trust-and-ownership foundation the whole ecosystem stands on.
