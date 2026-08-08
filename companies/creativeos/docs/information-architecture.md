# CreativeOS — Information Architecture

One navigation system across six products. The user's mental model is **"I'm in CreativeOS, and I
move between rooms,"** never "I'm switching apps."

---

## 1. The persistent shell

Every screen in every product renders inside one shell. The shell never reloads when you move
between products — only the product pane swaps.

```
┌──────────────────────────────────────────────────────────────────────┐
│  ◐ CreativeOS   [ ⌘K  Search everything… ]        🔔  ✉  ◍ profile ▾   │  ← top bar (global)
├────────────┬─────────────────────────────────────────────────────────┤
│  RAIL      │                                                          │
│            │                                                          │
│  ◈ Home    │                 PRODUCT PANE                             │
│  ◈ Frame   │           (the active product renders here)             │
│    Vault   │                                                          │
│  ◈ Film    │                                                          │
│    Crew    │                                                          │
│  ◈ Story   │                                                          │
│    Forge   │                                                          │
│  ◈ Rights  │                                                          │
│    Hub     │                                                          │
│  ◈ Creator │                                                          │
│    Stack   │                                                          │
│  ◈ OTT     │                                                          │
│    Studio  │                                                          │
│            │                                                          │
│  ⚙ Settings│                                                          │
└────────────┴─────────────────────────────────────────────────────────┘
```

**Global, always present (spine services surfaced in the UI):**

- **Command palette (⌘K)** — one search box over people, projects, IP, assets, everything.
- **Notifications (🔔)** — one tray, fed by every product via the event bus.
- **Messages (✉)** — one inbox; threads originate from any product.
- **Profile menu (◍)** — identity, wallet, settings. Same everywhere.
- **Product rail** — the six products + Home + Settings.

---

## 2. URL structure

Clean, predictable, product-prefixed. Public creator pages get a vanity path off the root.

```
/                         Home — cross-product dashboard
/@handle                  Public FrameVault creator page (shareable, no login)
/framevault               Your identity hub (private view of your profile)
/framevault/edit
/filmcrew                 Project & talent discovery
/filmcrew/projects/:id
/filmcrew/hire/:roleId
/rightsforge              Rights marketplace — assets + IP, one product, two deal modes
/rightsforge/listings/:id
/creatorstack            Challenges
/creatorstack/c/:id
/studio                   Workspaces
/studio/w/:id/p/:projectId
/search?q=…               Full search results
/notifications
/messages/:threadId
/settings/{profile|wallet|notifications|permissions}
```

---

## 3. Screen inventory (prototype scope)

Priority reflects the build order — FrameVault first because it's the root of the identity graph.

| Product | Key screens | Prototype priority |
|---|---|---|
| **Shell** | Top bar, rail, command palette, notification tray | **P0 — built first** |
| **FrameVault** | Public creator page, private hub, edit profile | **P0 — built first** |
| **Home** | Cross-product activity + suggestions | P1 |
| **FilmCrew** | Project board, project detail, applicant view | P1 |
| **RightsForge** | Marketplace grid (asset + IP modes), listing detail, license/deal flow | P2 |
| **CreatorStack** | Challenge list, challenge detail, submission | P2 |
| **OTT Studio** | Workspace, project canvas, AI job panel | P2 |

---

## 4. Cross-product surfaces (the "one platform" proof)

These three surfaces are where consolidation pays off — each one spans every product:

1. **Home dashboard** — a single feed: a FilmCrew offer, a RightsForge royalty, a CreatorStack
   deadline, a RightsForge IP inquiry, all in one place because they all flow through the event bus.
2. **Command palette (⌘K)** — type a name → see their FrameVault profile, their FilmCrew projects,
   their RightsForge listings, in one ranked list. One index, many products.
3. **The profile menu** — wallet balance aggregates earnings from FilmCrew + RightsForge (assets and
   IP) + CreatorStack. One wallet, three income streams.

If these three feel seamless, the platform thesis is proven. If they feel bolted-on, it isn't.

---

## 5. Navigation principles

- **The shell is permanent.** Moving products swaps the pane, never the chrome.
- **Identity is one click away everywhere.** The profile menu and ⌘K are on every screen.
- **No dead ends.** Every entity (person, project, asset, IP, challenge) links to its canonical
  page, and every canonical page links back to the actor's FrameVault profile.
- **Public vs. private is explicit.** `/@handle` is the shareable public face; `/framevault` is the
  owner's private control panel over that same identity.
