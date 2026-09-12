# Port Registry — TypeScript/Next.js Rebuild

This is a fresh port block for the ground-up rewrite. It intentionally avoids every
range documented or actually used by the legacy Flask portfolio (now archived under
`_legacy-flask-archive/`) and by the separate `ott-sovereign-stack` project:

- `5000-5109` — claimed live by the external `ott-sovereign-stack` project.
- `5300-5320` — the legacy Flask portfolio's `run_all.py` / Gateway config block.
- `3000`, `8080` — common local dev defaults, avoided for clarity when running both
  stacks side by side during the transition.

Each app's own `.env`/`PORT` default (in its `package.json` `dev` script) is the actual
source of truth when run standalone — this table is the registry, not an enforcement
mechanism.

| Port | App           | Package                          |
|------|---------------|-----------------------------------|
| 5500 | Gateway       | `apps/gateway`                    |
| 5501 | Canonlock     | `apps/canonlock`                  |
| 5502 | Veridact      | `apps/veridact`                   |
| 5503 | Story Atlas   | `apps/story-atlas`                |
| 5504 | FrameVault    | `apps/framevault`                 |
| 5505 | FilmCrew      | `apps/filmcrew`                   |
| 5506 | RightsForge   | `apps/rightsforge`                |
| 5507 | CreatorStack  | `apps/creatorstack`               |
| 5508 | OTT Studio    | `apps/studio`                     |

`5509-5511` are reserved/free for future use within this project.

## Running an app standalone

```bash
npm install
npm run dev -w canonlock
```

## Running everything built so far

```bash
npm run dev
```

Runs every scaffolded app concurrently (via `concurrently`), each on its own port above.
