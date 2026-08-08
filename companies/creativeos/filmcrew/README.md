# FilmCrew — CreativeOS

The **collaboration / hiring** layer of CreativeOS, and the proof of the platform thesis: when you
hire someone here, a **verified credit lands on their FrameVault automatically** — two separate apps,
two separate databases, one connected platform.

## What it does

- Shows an open production role (“Halcyon” — Director of Photography) with ranked applicants.
- **Hire** an applicant → FilmCrew marks the hire in its own database, then calls **FrameVault's API**
  with a shared service key and writes a `hire.completed` credit (a 5★ verified review + a reputation
  event) onto that creator's FrameVault profile.
- Hire **OTT** (who has a FrameVault identity), then open their FrameVault page to see the new credit.

This is the cross-product "magic moment" — the whole reason CreativeOS is one platform, not six.

## The seam (how it stays clean)

FilmCrew **never touches FrameVault's database.** It makes an HTTP call to FrameVault's `/api/credit`
endpoint and presents `X-Service-Key`. In the full build this credit travels over the shared event
bus (`hire.completed`); this HTTP call is that same contract, made real. See
`framevault/ARCHITECTURE.md` for the isolation + integration rules.

## Run it (locally)

FilmCrew needs FrameVault running so it has somewhere to send the credit.

1. **Terminal 1 — FrameVault** (port 5001):
   ```
   cd ../framevault
   python app.py
   ```
2. **Terminal 2 — FilmCrew** (port 5002):
   ```
   cd ../filmcrew
   pip install -r requirements.txt
   python app.py
   ```
3. Open **http://127.0.0.1:5002**, hire **OTT**, then click **“See it on FrameVault ↗”**.

## Isolation (the CreativeOS convention)

| | |
|---|---|
| Folder | `creativeos/filmcrew/` |
| Database | `filmcrew.db` (its own — never shared) |
| Port | **5002** |
| Talks to FrameVault via | `FRAMEVAULT_URL` (default `http://127.0.0.1:5001`) + `FV_SERVICE_KEY` |

Config via env: `FRAMEVAULT_URL`, `FV_SERVICE_KEY` (must match FrameVault's), `FC_DB`.
