# Anti-Sovereign

A portfolio of independent product MVPs exploring cryptographic proof, provenance, and
verified origin — Canonlock (IP registry with Merkle proofs), Veridact (capture
attestation and watermarking), and the CreativeOS suite (Story Atlas, FrameVault,
FilmCrew, RightsForge, CreatorStack, OTT Studio), fronted by a minimal Gateway hub.

This is a ground-up TypeScript/Next.js rewrite. The previous Flask/Python implementation
is preserved under [`_legacy-flask-archive/`](_legacy-flask-archive/) as a product-spec
reference only — its code was not ported, and none of it runs as part of this stack.

## Stack

- **TypeScript** end to end, **Next.js 15** (App Router) per app.
- **SQLite per app** via **Drizzle ORM** (`better-sqlite3`) — every product owns its own
  local database; no shared cloud database.
- **Tailwind CSS + shadcn/ui**, driven by the shared `@anti-sovereign/design-system`
  package (tokens, Tailwind preset, fonts) so every app shares one visual language with
  its own single accent color.
- **Zod** for all input validation.
- **Vitest** for unit tests, **Playwright** for e2e + PWA install verification.
- Every app ships as a real installable PWA (manifest, icons, offline shell) — "apps, not
  websites."

## Layout

```
apps/
  gateway/       Live status dashboard + links for every app below
  canonlock/     SHA-256 IP registry, Merkle inclusion proofs, certificates
  veridact/      Capture attestation + watermarking
  story-atlas/   Worldbuilding / canon engine
  framevault/    Dailies/asset vault; ecosystem identity + reputation hub
  filmcrew/      Crew & project collaboration
  rightsforge/   Rights & licensing workflows
  creatorstack/  Creator tooling
  studio/        Production workspace
packages/
  design-system/ Shared design tokens, Tailwind preset, fonts, app registry
  frame-client/  Typed SDK for calling FrameVault's identity/reputation API
  config/        Shared tsconfig
```

See [`PORTS.md`](PORTS.md) for the port registry.

## Running

```bash
npm install
npm run dev              # every app built so far
npm run dev -w canonlock # a single app
```

Each app writes its own SQLite file on first run (gitignored). Run its Drizzle
migrations first: `npm run db:migrate -w <app>`.
