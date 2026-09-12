# Deploying CreativeOS — from your laptop to the internet

Plain-English guide. Right now FrameVault and FilmCrew run on `localhost`, which means **your
computer only**. This is how they get real web addresses that anyone can visit.

You do not need to be a sysadmin. The whole thing is roughly: *push code to GitHub → point a host at
it → set a few settings → attach a domain.*

---

## 0. Before you deploy — the safety checklist

Do not skip these. A public URL means the whole internet can reach it.

| Check | Why | How |
|---|---|---|
| **Turn off the demo login** | Otherwise `ott` / `framevault` is a public backdoor into your own profile | Set env `FV_DEMO=0` and `FV_DEMO_PASSWORD=<something long and random>` |
| **Set a stable secret** | It signs both login sessions *and* provenance signatures. If it changes, everyone is logged out and old signatures stop validating | Set env `FV_SECRET=<long random string>` |
| **Set a real service key** | It's the password FilmCrew uses to write credits into FrameVault. The default is a public dev value | Set env `FV_SERVICE_KEY=<long random string>` on **both** apps — they must match exactly |
| **Decide where data lives** | The free tier wipes the disk on every deploy | Attach a persistent disk (below), or move to Postgres |

Generate a good random value for any of the above:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## 1. Put the code on GitHub

Your repo is already on GitHub (`OTT55/ott-sovereign-stack`), so this is just:

```bash
git add -A
git commit -m "Deploy-ready"
git push
```

Hosts read your code straight from GitHub and redeploy every time you push.

---

## 2. Deploy FrameVault (Render — recommended)

I've already written a blueprint file, `framevault/render.yaml`, so Render can configure itself.

**Why Render:** free tier, beginner-friendly, supports Python, gives you HTTPS automatically, and can
mount a persistent disk. (Railway or Fly.io work the same way if you prefer.)

1. Go to **render.com** → sign up with your GitHub account.
2. **New → Blueprint** → pick the `ott-sovereign-stack` repo.
3. Render reads `companies/creativeos/framevault/render.yaml` and pre-fills everything:
   - **Build:** `pip install -r requirements.txt`
   - **Start:** `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2`
   - **`FV_SECRET`** — auto-generated and kept stable ✅
   - **`FV_DB`** → `/var/data/framevault.db` on a **1 GB persistent disk** ✅ (survives redeploys)
4. Before hitting create, add two more environment variables:
   - `FV_DEMO` = `0`
   - `FV_SERVICE_KEY` = *(your long random string — save it, FilmCrew needs the same one)*
5. **Create** and wait ~2 minutes.

You'll get a URL like `https://framevault.onrender.com` — **already HTTPS**. Visit `/signup`, make
your real account, and you're live.

> **Note on `gunicorn`:** that's the production web server. The `python app.py` you use locally is a
> *development* server — fine for your laptop, not for real traffic. Nothing to install by hand; it's
> in `requirements.txt`.

### If you'd rather click it yourself (manual setup)

Skip the blueprint and do it by hand:

1. **New → Web Service** → pick the repo.
2. **Root Directory:** `companies/creativeos/framevault`
3. **Build command:** `pip install -r requirements.txt`
4. **Start command:** `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2`
5. **Environment:** add `FV_SECRET`, `FV_SERVICE_KEY`, `FV_DEMO=0`, and `FV_DB=/var/data/framevault.db`
6. **Disks:** add a 1 GB disk mounted at `/var/data` (so the database survives redeploys)

### About that `--workers 2`

That runs **two copies** of the app behind the scenes. Because the apps are *stateless* (they keep
nothing important in memory), you raise that number — and the plan — to handle more traffic, with
**no code changes**. That's the scaling path from `ARCHITECTURE.md` in practice.

Keep `FV_SECRET` private: anyone holding it could forge provenance signatures. That's exactly why
`.fv_secret` and `framevault.db` are git-ignored and never committed.

---

## 3. Deploy FilmCrew (the second service)

Same process, one extra step — it has to know where FrameVault lives.

1. **New → Web Service** → same repo.
2. Set **Root Directory** to `companies/creativeos/filmcrew`.
3. **Build:** `pip install -r requirements.txt`
   **Start:** `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2`
4. Environment variables:
   - `FRAMEVAULT_URL` = `https://framevault.onrender.com` *(your real FrameVault URL)*
   - `FV_SERVICE_KEY` = *(the **exact same** value you set on FrameVault)*

That's the integration seam going live: two separately-deployed apps, on different URLs, talking over
HTTPS. If the keys don't match, the hire still succeeds but the credit is refused — by design.

---

## 4. Your own domain + HTTPS

1. Buy a domain (Namecheap, Cloudflare, Porkbun — ~£10/year). Say `creativeos.com`.
2. In Render: your service → **Settings → Custom Domain** → add `id.creativeos.com`.
3. Render shows you a **CNAME** record. Add it at your domain registrar's DNS page.
4. Wait a few minutes. **HTTPS is issued automatically and free** (Let's Encrypt).

Matching the plan in `framevault/ARCHITECTURE.md`:

| App | Domain |
|---|---|
| FrameVault | `id.creativeos.com` |
| FilmCrew | `crew.creativeos.com` |
| Main shell (later) | `app.creativeos.com` |

---

## 5. When to move off SQLite

SQLite (one file) is genuinely fine for your first users — with the persistent disk above, nothing is
lost. Move to **PostgreSQL** when either becomes true:

- You run **more than one server** (SQLite allows only one writer).
- You want **automatic backups and point-in-time restore**.

The migration is a **copy, not a rewrite** — same tables, copy the rows, change one setting. Render
offers managed Postgres; add it when you need it, not before.

---

## 6. What it costs

| Stage | Cost |
|---|---|
| Right now (laptop) | **£0** |
| First deploy (Render free tier) | **£0** — sleeps when idle, wakes on visit |
| Always-on + persistent disk | ~**£5–8/month per service** |
| Domain | ~**£10/year** |
| Serious scale (Postgres, multiple servers) | grows with usage |

Because files are hashed in the browser and never uploaded, you skip the two things that make creator
platforms expensive: **storage and bandwidth for big video files.**

---

## 7. If something breaks

| Symptom | Likely cause |
|---|---|
| "Application failed to respond" | Start command wrong — must bind `0.0.0.0:$PORT`, not a fixed port |
| Everyone logged out after a deploy | `FV_SECRET` not set, so a new one was generated |
| Data vanished after a deploy | No persistent disk — set `FV_DB` to a mounted path |
| Hire works but no credit appears | `FV_SERVICE_KEY` mismatch between the two apps, or wrong `FRAMEVAULT_URL` |
| Old provenance shows "signature invalid" | `FV_SECRET` changed — signatures are bound to it |

Check the **Logs** tab in Render first; it almost always says exactly what went wrong.

---

## The honest summary

Deploying is a genuine step, but it is **not** a rewrite — the apps were built for it from day one:
config comes from environment variables, the port isn't hardcoded, the database path is swappable,
and each product deploys independently without touching the others. That's why this guide is short.
