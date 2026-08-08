# CreativeOS — Database Schema Proposal

Postgres, one logical database, organized **schema-per-domain**. Shared-spine tables are the
gravitational center; every product table references `users` and, usually, `creator_profiles`.

Notation: `PK` primary key, `FK →` foreign key, `?` nullable. IDs are UUIDs unless noted.

---

## Spine — Identity & Profiles

```
users
  id                PK
  email             unique
  password_hash     ?           -- null when social-only
  display_name
  handle            unique      -- @handle, used in URLs
  auth_provider     enum(local, google, apple)
  created_at, updated_at

creator_profiles                -- FrameVault's core record; 1:1 with users
  id                PK
  user_id           FK → users  unique
  headline                       -- "Cinematographer · Deakins-influenced"
  bio
  location          ?
  availability      enum(open, selective, booked)
  verified          bool         -- identity/portfolio verification
  reputation_score  numeric      -- denormalized from reputation service
  created_at, updated_at

profile_skills
  id                PK
  profile_id        FK → creator_profiles
  skill                          -- "Color grading"
  level             enum(beginner, intermediate, expert)

portfolio_items                 -- verified work shown on the public page
  id                PK
  profile_id        FK → creator_profiles
  title, description ?
  media_id          FK → media_assets
  role                           -- creator's role on this piece
  source_product    ?            -- which product this came from, if any
  source_ref        ?            -- e.g. the FilmCrew project id
  provenance_id     FK → provenance_records ?
  created_at

ai_contributions                -- transparent AI-usage history (trust signal)
  id                PK
  profile_id        FK → creator_profiles
  work_ref                       -- portfolio_item or project
  description                    -- "AI used for rough color pass; hand-finished"
  disclosed_at
```

---

## Spine — Permissions

```
roles
  id  PK   ·  key (unique, e.g. "producer")  ·  name

capabilities
  id  PK   ·  key (unique, e.g. "hire.create")

role_capabilities
  role_id  FK → roles   ·   capability_id  FK → capabilities

user_roles                      -- coarse RBAC
  user_id  FK → users   ·   role_id  FK → roles

resource_grants                 -- fine ABAC: per-resource sharing
  id            PK
  user_id       FK → users
  resource_type                 -- "project" | "ip_listing" | "workspace"
  resource_id
  capability_key                -- "workspace.edit"
  granted_by    FK → users
  expires_at    ?
```

---

## Spine — shared services (abbreviated)

```
notifications
  id PK · user_id FK · type · payload(jsonb) · read_at ? · created_at

notification_prefs
  user_id FK · channel enum(inapp,email,push) · type · enabled bool

messages / message_threads
  thread: id PK · subject ? · created_at
  thread_participants: thread_id FK · user_id FK · last_read_at ?
  message: id PK · thread_id FK · sender_id FK · body · created_at

media_assets
  id PK · owner_id FK → users · kind enum(image,video,audio,pdf,other)
  storage_key · mime · bytes · duration_s ? · preview_key ? · created_at

reviews
  id PK · subject_type · subject_id · author_id FK → users
  rating int(1..5) · body ? · context_ref -- what transaction earned the review
  created_at

reputation_events              -- append-only; score is derived from these
  id PK · profile_id FK → creator_profiles · kind · weight numeric
  source_product · source_ref · created_at

provenance_records             -- content authentication / audit
  id PK · content_hash · owner_id FK → users · asserted_at
  source_product · source_ref · signature ?

events                         -- the event bus / outbox (the glue)
  id PK · type -- "hire.completed" · actor_id FK → users ?
  payload(jsonb) · created_at · processed_at ?

wallet_accounts   id PK · owner_id FK → users · balance_cents · currency
ledger_entries    id PK · account_id FK · amount_cents · kind · ref · created_at
subscriptions     id PK · user_id FK · plan · status · current_period_end
```

---

## Product — FilmCrew (collaboration / hiring)

```
projects            id PK · owner_id FK → users · title · summary · status
                    enum(draft,open,in_production,wrapped) · budget_cents ?
project_roles       id PK · project_id FK · title · skill · rate_cents ? · filled bool
applications        id PK · role_id FK → project_roles · applicant_id FK → users
                    status enum(applied,shortlisted,offered,hired,declined)
contracts           id PK · project_id FK · creator_id FK → users · terms
                    status enum(draft,signed,delivered,paid) · escrow_ref ?
```
On `contracts.status → paid`, emit `hire.completed` → FrameVault, Reputation, Payments, Notifications.

---

## Product — RightsForge (rights marketplace: assets + IP)

RightsHub (asset licensing) and StoryForge (IP marketplace) turned out to be the same engine with
two deal modes, so they're one product, one schema, distinguished by `listing_type`. See
`rightsforge/app.py` for the shipped version of this table set.

```
listings            id PK · seller_id FK → users · listing_type enum(asset,ip)
                    title · category            -- asset: music/sfx/lut/vfx/template/motion/voice/
                                                 -- footage; ip: script/novel/comic/pilot/game_concept/idea
                    description · provenance_id FK → provenance_records ?
                    status enum(listed,optioned,sold)   -- ip only; assets stay 'listed'

asset_tiers          id PK · listing_id FK · name · price_cents          -- asset mode only
royalty_splits        id PK · listing_id FK · payee_id FK → users · pct numeric   -- asset mode only
ip_terms              id PK · listing_id FK · kind enum(option,license,purchase) · price_cents  -- ip mode only

deals                id PK · listing_id FK · buyer_id FK → users · kind
                    -- asset: the tier name, always 'paid' (instant)
                    -- ip: option|license|purchase, status enum(proposed,agreed,paid)
                    price_cents · created_at
```
On an asset deal, split payment via `royalty_splits` → Payments; emit `asset.licensed`.
On an IP deal reaching `paid`, emit `ip.optioned` / `ip.licensed` / `ip.purchased` → Payments
(escrow release), Notifications, FrameVault history — and lock the listing (exclusive).

---

## Product — CreatorStack (competitions)

```
challenges          id PK · sponsor_id FK → users · title · brief · prize_cents
                    submit_deadline · status enum(open,judging,awarded,funded)
submissions         id PK · challenge_id FK · creator_id FK → users
                    concept_media_id FK → media_assets ? · pitch
awards              id PK · challenge_id FK · submission_id FK · funding_cents ?
```
On award, emit `challenge.won` → Reputation, FrameVault, Payments.

---

## Product — OTT Studio (workspace)

```
workspaces          id PK · owner_id FK → users · name
workspace_members   workspace_id FK · user_id FK · role enum(owner,editor,viewer)
studio_projects     id PK · workspace_id FK · name · status · created_at
studio_assets       id PK · project_id FK · media_id FK → media_assets · label
ai_jobs             id PK · project_id FK · kind · status
                    enum(queued,running,done,failed) · params(jsonb) · result_ref ?
```
Sharing uses spine `resource_grants`; publishing emits `project.published` → Search, FrameVault.

---

## The one rule that keeps it coherent

Every product table above eventually points back to **`users`** and, for creative work, to
**`creator_profiles`**. No product owns identity, payments, reputation, or provenance — it references
the spine. That single constraint is what makes six products behave as one platform rather than six
databases wearing a trench coat.
