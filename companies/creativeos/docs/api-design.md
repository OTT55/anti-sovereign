# CreativeOS — API Design

REST + JSON over one gateway. Products never call each other's databases; they call spine services,
and cross-product effects propagate through the event bus. This document sketches the surface, not
an exhaustive spec.

Conventions:

- Base: `/api/v1`. All routes require a session unless marked **public**.
- Auth: `Authorization: Bearer <session token>`. The gateway resolves the actor and coarse role.
- IDs are UUIDs. Timestamps are ISO-8601 UTC. Money is integer cents + currency.
- Errors: `{ "error": { "code", "message", "details"? } }` with standard HTTP status.
- Pagination: `?cursor=&limit=` → `{ data, next_cursor }`.

---

## Spine — Identity & Profiles (FrameVault's backend)

```
GET    /profiles/@:handle              (public) full public creator page
GET    /profiles/me                    the caller's profile
PATCH  /profiles/me                    edit headline, bio, availability
GET    /profiles/me/skills   · POST · DELETE /profiles/me/skills/:id
GET    /profiles/:id/portfolio
POST   /profiles/me/portfolio          { title, media_id, role, source_ref? }
GET    /profiles/:id/ai-contributions  transparent AI-usage history
```

## Spine — cross-cutting services

```
# Search (unified index)
GET  /search?q=&types=people,projects,ip,assets,challenges   ranked, grouped by type

# Notifications
GET   /notifications?unread=true
POST  /notifications/:id/read
GET   /notifications/prefs · PATCH /notifications/prefs

# Messaging
GET   /threads · POST /threads { participant_ids, subject? }
GET   /threads/:id/messages · POST /threads/:id/messages { body }

# Media
POST  /media          multipart → { id, kind, preview_url }
GET   /media/:id

# Reviews & reputation
POST  /reviews        { subject_type, subject_id, rating, body?, context_ref }
GET   /profiles/:id/reputation           derived score + recent events

# Payments & wallet
GET   /wallet · GET /wallet/ledger
POST  /payments/checkout   { kind, ref }          → escrow/checkout session
GET   /subscriptions · POST /subscriptions { plan }

# Permissions
GET   /permissions/me                    roles + capabilities
POST  /grants   { resource_type, resource_id, user_id, capability }
```

## Products (representative endpoints)

```
# FilmCrew
GET  /filmcrew/projects?status=open · POST /filmcrew/projects
POST /filmcrew/roles/:id/apply
POST /filmcrew/contracts/:id/sign · POST /filmcrew/contracts/:id/deliver
      → on paid, emits hire.completed

# RightsForge (rights marketplace — one product, two deal modes)
GET  /rightsforge/listings?mode=asset&kind=music · POST /rightsforge/listings { listing_type }
POST /rightsforge/listings/:id/license   { tier_id }              -- asset mode, instant
      → splits royalties, emits asset.licensed
POST /rightsforge/listings/:id/deal      { kind: option|license|purchase }   -- ip mode
POST /rightsforge/deals/:id/advance      -- proposed → agreed → paid
      → on paid, emits ip.optioned / ip.licensed / ip.purchased, locks the listing

# CreatorStack
GET  /creatorstack/challenges?status=open
POST /creatorstack/challenges/:id/submit
POST /creatorstack/challenges/:id/award   { submission_id }
      → emits challenge.won

# OTT Studio
GET  /studio/workspaces · POST /studio/workspaces
POST /studio/projects/:id/ai-jobs   { kind, params }   async → ai_jobs
POST /studio/projects/:id/publish
      → emits project.published
```

---

## Events (the async contract)

Every product write that other products should react to publishes an event. Subscribers are spine
services; products stay decoupled.

| Event | Emitted by | Subscribers react by |
|---|---|---|
| `hire.completed` | FilmCrew | FrameVault history · Reputation · Payments release · Notify |
| `asset.licensed` | RightsForge (asset mode) | Payments split · Provenance · FrameVault earnings · Notify |
| `ip.optioned` / `ip.licensed` / `ip.purchased` | RightsForge (IP mode) | Payments escrow · FrameVault history · Notify |
| `challenge.won` | CreatorStack | Reputation · FrameVault history · Payments prize · Notify |
| `project.published` | OTT Studio | Search index · FrameVault portfolio · Provenance |
| `review.created` | any | Reputation recompute · Notify subject |

Event envelope:

```json
{
  "id": "uuid",
  "type": "hire.completed",
  "actor_id": "uuid",
  "occurred_at": "2026-07-20T12:00:00Z",
  "payload": { "creator_id": "…", "project_id": "…", "role": "DP", "rating": 5 }
}
```

Consumers must be **idempotent** (dedupe on `id`) and tolerate out-of-order delivery — the price of
an eventually-consistent, decoupled ecosystem, and the reason cross-product features are easy to add.
