"""
FrameVault — the identity + provenance layer of CreativeOS.

This is the first *real* CreativeOS product, and it embodies the V1 trust wedge:
"AI made creation free; we build the trust layer." FrameVault answers the questions that
get MORE valuable as AI content floods everything —

    who made this, when, with whom, and how much of it was AI?

How provenance works here (and why it's genuinely trustworthy):
  * The creator picks a file. The browser computes its SHA-256 hash locally (Web Crypto API).
  * Only the hash + metadata are sent to the server — never the file itself. FrameVault can
    prove a specific file was registered by a specific creator at a specific time without ever
    seeing, storing, or being able to leak the work. That is real, privacy-preserving proof
    of authorship.
  * The server records the hash, a unique registry ID, a UTC timestamp, the contributors, and
    a transparent AI-disclosure, then signs the record (HMAC-SHA256). Anyone can later paste a
    hash (or drop the file) into /verify to check whether it is registered and to whom.

Honest scope notes (documented, not faked):
  * Auth is REAL: password signup/login with hashed passwords (werkzeug) and signed-cookie
    sessions. FrameVault is the identity layer, so it owns login — in the full ecosystem this same
    service issues the session every other product trusts. A demo account is seeded (see DEMO_LOGIN).
    Still to come: verified-identity checks (e.g. Stripe Identity) and per-creator signing keys.
  * The signature uses a local HMAC secret, not a per-user keypair. It's a real MAC that proves
    the record was issued by this FrameVault instance and hasn't been altered; production would
    move to per-creator asymmetric keys. Nothing here is a mock — the hashing, storage, signing,
    and verification are all real.

Isolation: FrameVault is its own service on its own port with its own database file. Per the
CreativeOS convention (see ARCHITECTURE.md), the main shell/gateway owns port 5000 and each product
gets its own port — FrameVault is 5001. No product ever touches another product's database.

Stack: Python Flask + SQLite, vanilla HTML/CSS/JS front-end. No paid API required.
Run:   pip install -r requirements.txt  &&  python app.py   ->  http://127.0.0.1:5001
"""

import os
import re
import hmac
import hashlib
import secrets
import sqlite3
import datetime
from functools import wraps

from flask import (
    Flask, request, jsonify, render_template, redirect, url_for, abort, g, session
)
from werkzeug.security import generate_password_hash, check_password_hash

APP_DIR = os.path.dirname(os.path.abspath(__file__))
# DB path is overridable so a deploy can point it at a persistent disk (env FV_DB).
DB_PATH = os.environ.get("FV_DB", os.path.join(APP_DIR, "framevault.db"))
SECRET_PATH = os.path.join(APP_DIR, ".fv_secret")

# Port comes from the environment so you never edit code to move it.
# Registered in /PORTS.md — CreativeOS owns the 5000–5099 block; FrameVault is 5001.
PORT = int(os.environ.get("FRAMEVAULT_PORT", 5001))

SEED_OWNER_ID = 1        # the demo user (OTT) created on first run
# Demo account. In production set FV_DEMO=0 (hides the hint) and FV_DEMO_PASSWORD=<strong value>,
# otherwise a deployed instance ships a publicly-known login. See DEPLOY.md.
DEMO_PASSWORD = os.environ.get("FV_DEMO_PASSWORD", "framevault")
DEMO_LOGIN = ("ott", DEMO_PASSWORD)
SHOW_DEMO = os.environ.get("FV_DEMO", "1") == "1"
# Shared secret other CreativeOS products present to write credits into FrameVault
# (the event seam). Set FV_SERVICE_KEY in production; products send it as X-Service-Key.
SERVICE_KEY = os.environ.get("FV_SERVICE_KEY", "creativeos-dev-service-key")
HANDLE_RE = re.compile(r"^[a-z0-9_]{2,20}$")   # allowed public @handles
HASH_RE = re.compile(r"^[0-9a-f]{64}$")  # a valid lowercase SHA-256 hex digest

app = Flask(__name__)


@app.template_filter("gbp")
def gbp(pence):
    """Integer pence -> a display string like £1,200 or £29.50."""
    pounds = (pence or 0) / 100
    return f"£{pounds:,.0f}" if pounds == int(pounds) else f"£{pounds:,.2f}"


# --------------------------------------------------------------------------- #
#  Signing secret (stable across restarts; see the module docstring)          #
# --------------------------------------------------------------------------- #
def load_secret():
    # Production sets a stable FV_SECRET env var (survives redeploys on ephemeral hosts,
    # keeping sessions + signatures valid). Locally we persist one to a gitignored file.
    env = os.environ.get("FV_SECRET")
    if env:
        return env.encode()
    if os.path.exists(SECRET_PATH):
        with open(SECRET_PATH, "rb") as fh:
            return fh.read()
    s = secrets.token_bytes(32)
    with open(SECRET_PATH, "wb") as fh:
        fh.write(s)
    return s


SECRET = load_secret()
# The same secret keys signed login sessions (Flask's signed cookie). Rotating the
# secret invalidates sessions AND provenance signatures — fine for a single instance.
app.secret_key = SECRET


# Every field below is bound into the signature. Altering ANY of them (e.g.
# quietly changing an AI disclosure from "AI generated" to "No AI used") breaks
# the signature — which is exactly what makes the record tamper-evident.
SIGNED_FIELDS = (
    "content_hash", "registry_id", "owner_id", "created_at",
    "title", "role", "contributors", "ai_disclosure", "source",
)


def canonical(rec):
    """Deterministic string over all signed fields (order fixed, keys named)."""
    return "|".join(f"{k}={rec[k]}" for k in SIGNED_FIELDS)


def sign(rec):
    """Real HMAC-SHA256 over the full canonical record — not just the hash."""
    return hmac.new(SECRET, canonical(rec).encode(), hashlib.sha256).hexdigest()


def new_registry_id():
    year = datetime.datetime.now().strftime("%Y")
    return f"FV-{year}-{secrets.token_hex(3).upper()}"


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- #
#  Database                                                                    #
# --------------------------------------------------------------------------- #
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  email         TEXT UNIQUE,
  display_name  TEXT NOT NULL,
  handle        TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL DEFAULT '',
  verified      INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS creator_profiles (
  user_id       INTEGER PRIMARY KEY REFERENCES users(id),
  headline      TEXT DEFAULT '',
  bio           TEXT DEFAULT '',
  location      TEXT DEFAULT '',
  availability  TEXT DEFAULT 'open',          -- open | selective | booked
  updated_at    TEXT
);

CREATE TABLE IF NOT EXISTS profile_skills (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id       INTEGER NOT NULL REFERENCES users(id),
  skill         TEXT NOT NULL,
  level         TEXT NOT NULL DEFAULT 'Intermediate'
);

-- Each registered work is BOTH a portfolio piece and a signed provenance record.
CREATE TABLE IF NOT EXISTS provenance_records (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  registry_id   TEXT UNIQUE NOT NULL,
  owner_id      INTEGER NOT NULL REFERENCES users(id),
  content_hash  TEXT NOT NULL,               -- client-computed SHA-256
  filename      TEXT DEFAULT '',
  mime          TEXT DEFAULT '',
  bytes         INTEGER DEFAULT 0,
  title         TEXT NOT NULL,
  role          TEXT DEFAULT '',
  contributors  TEXT DEFAULT '',
  ai_disclosure TEXT DEFAULT '',             -- transparent "what AI touched this"
  source        TEXT DEFAULT 'FrameVault',
  created_at    TEXT NOT NULL,
  signature     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_prov_hash ON provenance_records(content_hash);
CREATE INDEX IF NOT EXISTS idx_prov_owner ON provenance_records(owner_id);

CREATE TABLE IF NOT EXISTS reviews (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  subject_user  INTEGER NOT NULL REFERENCES users(id),
  author_name   TEXT NOT NULL,
  author_handle TEXT DEFAULT '',
  rating        INTEGER NOT NULL,            -- 1..5
  body          TEXT DEFAULT '',
  context       TEXT DEFAULT '',
  created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reputation_events (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id       INTEGER NOT NULL REFERENCES users(id),
  kind          TEXT NOT NULL,
  weight        REAL NOT NULL DEFAULT 1,
  source        TEXT DEFAULT '',
  created_at    TEXT NOT NULL
);

-- The other half of the wallet: reputation_events is what you EARNED (money in).
-- ledger_spend is what you PAID OUT (money out) — the payer's side of the same
-- transaction, written atomically by the same /api/credit call. Without this,
-- a contract/deal/prize only ever proved one party's side of the story.
CREATE TABLE IF NOT EXISTS ledger_spend (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id       INTEGER NOT NULL REFERENCES users(id),
  counterparty  TEXT DEFAULT '',    -- handle of who was paid
  kind          TEXT NOT NULL,
  source        TEXT DEFAULT '',
  amount_pence  INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _migrate(db):
    """CREATE TABLE IF NOT EXISTS doesn't add columns to a table that already
    exists from an older version of SCHEMA — amount_pence postdates the
    original reputation_events table. Add it if missing."""
    cols = {row[1] for row in db.execute("PRAGMA table_info(reputation_events)")}
    if "amount_pence" not in cols:
        db.execute("ALTER TABLE reputation_events ADD COLUMN amount_pence INTEGER DEFAULT 0")


def init_db():
    """Create tables and seed a populated demo profile on first run."""
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    _migrate(db)
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        seed(db)
    db.commit()
    db.close()


def seed(db):
    ts = now_iso()
    db.execute(
        "INSERT INTO users (id, email, display_name, handle, password_hash, verified, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (SEED_OWNER_ID, "ott@creativeos.app", "OTT", "ott",
         generate_password_hash(DEMO_LOGIN[1]), 1, ts),
    )
    db.execute(
        "INSERT INTO creator_profiles (user_id, headline, bio, location, availability, updated_at) "
        "VALUES (?,?,?,?,?,?)",
        (
            SEED_OWNER_ID,
            "Cinematographer · Director of Photography",
            "Founder of CreativeOS and a working DP. I light for shadow and shoot for tone. "
            "Every piece here carries a signed provenance record — proof of authorship you can verify.",
            "London",
            "selective",
            ts,
        ),
    )
    for skill, level in [
        ("Cinematography", "Expert"),
        ("Lighting", "Expert"),
        ("Color / grading", "Advanced"),
        ("Camera operation", "Advanced"),
        ("Steadicam", "Intermediate"),
    ]:
        db.execute(
            "INSERT INTO profile_skills (user_id, skill, level) VALUES (?,?,?)",
            (SEED_OWNER_ID, skill, level),
        )

    # Seed provenance records with REAL SHA-256 hashes (of descriptive seed content),
    # so /verify genuinely works against them out of the box.
    seed_works = [
        ("Halcyon — camera test", "Director of Photography", "OTT, Nadia Okonkwo",
         "AI used for a proxy transcode only (disclosed). No generative AI. Every frame shot on set.",
         "OTT Studio"),
        ("Nightshift — short film", "Director of Photography", "OTT, Maya Rún (dir.)",
         "No AI used.", "FilmCrew"),
        ("Umber — LUT pack", "Colorist / author", "OTT, Kojo Mensah (grade assist)",
         "Fully hand-authored. No generative AI.", "RightsForge"),
        ("The Archivist — key art", "Concept / author", "OTT",
         "AI used for early moodboard brainstorming only; final art hand-made. Disclosed.", "RightsForge"),
    ]
    for i, (title, role, contributors, ai, source) in enumerate(seed_works):
        content = f"seed::{title}::{i}".encode()
        content_hash = hashlib.sha256(content).hexdigest()
        rid = new_registry_id()
        created = now_iso()
        rec = {
            "content_hash": content_hash, "registry_id": rid, "owner_id": SEED_OWNER_ID,
            "created_at": created, "title": title, "role": role,
            "contributors": contributors, "ai_disclosure": ai, "source": source,
        }
        db.execute(
            "INSERT INTO provenance_records "
            "(registry_id, owner_id, content_hash, filename, mime, bytes, title, role, "
            " contributors, ai_disclosure, source, created_at, signature) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rid, SEED_OWNER_ID, content_hash, f"{title.split(' — ')[0].lower()}.mov",
             "video/quicktime", 0, title, role, contributors, ai, source, created,
             sign(rec)),
        )

    for name, handle, rating, body, ctx in [
        ("Studio Kestrel", "kestrel", 5,
         "One of the most prepared DPs we've worked with. Every setup was blocked before we rolled.",
         "Hired for “Halcyon” · via FilmCrew"),
        ("Maya Rún", "maya", 5,
         "Understood the tone from the first conversation. The Umber grade was exactly right.",
         "Collaborated on “The Archivist” · via RightsForge"),
        ("Theo Marchetti", "theo", 5,
         "Great eye and generous with feedback. Would absolutely work together again.",
         "“Cold Open” · via CreatorStack"),
    ]:
        db.execute(
            "INSERT INTO reviews (subject_user, author_name, author_handle, rating, body, context, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (SEED_OWNER_ID, name, handle, rating, body, ctx, ts),
        )

    for kind, weight, source in [
        ("hire.completed", 5, "FilmCrew"),
        ("asset.licensed", 3, "RightsForge"),
        ("ip.optioned", 4, "RightsForge"),
    ]:
        db.execute(
            "INSERT INTO reputation_events (user_id, kind, weight, source, created_at) "
            "VALUES (?,?,?,?,?)",
            (SEED_OWNER_ID, kind, weight, source, ts),
        )


# --------------------------------------------------------------------------- #
#  Read helpers                                                                #
# --------------------------------------------------------------------------- #
def fetch_user(handle=None, user_id=None):
    db = get_db()
    if handle is not None:
        return db.execute("SELECT * FROM users WHERE handle = ?", (handle,)).fetchone()
    return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def profile_bundle(user):
    """Everything a public page or dashboard needs for one creator."""
    db = get_db()
    uid = user["id"]
    profile = db.execute(
        "SELECT * FROM creator_profiles WHERE user_id = ?", (uid,)
    ).fetchone()
    skills = db.execute(
        "SELECT id, skill, level FROM profile_skills WHERE user_id = ? ORDER BY id", (uid,)
    ).fetchall()
    records = db.execute(
        "SELECT * FROM provenance_records WHERE owner_id = ? ORDER BY id DESC", (uid,)
    ).fetchall()
    reviews = db.execute(
        "SELECT * FROM reviews WHERE subject_user = ? ORDER BY id DESC", (uid,)
    ).fetchall()
    rep = db.execute(
        "SELECT AVG(rating) a, COUNT(*) n FROM reviews WHERE subject_user = ?", (uid,)
    ).fetchone()
    reputation = round(rep["a"], 1) if rep["a"] is not None else None
    # The wallet: lifetime sum of every paid credit (RightsForge licenses/deals,
    # CreatorStack awards, FilmCrew contracts). There is no payout mechanism
    # anywhere in the ecosystem yet, so this is a running total, not a
    # withdrawable balance — the UI says "earned", not "available".
    earned = db.execute(
        "SELECT COALESCE(SUM(amount_pence), 0) p FROM reputation_events WHERE user_id = ?", (uid,)
    ).fetchone()["p"]
    earnings = db.execute(
        "SELECT kind, weight, source, amount_pence, created_at FROM reputation_events "
        "WHERE user_id = ? AND amount_pence > 0 ORDER BY id DESC", (uid,)
    ).fetchall()
    # The payer's side of the same ledger — what this creator has paid out
    # across every marketplace-shaped product (FilmCrew contracts, RightsForge
    # deals, CreatorStack prizes), not just what they've earned.
    spent = db.execute(
        "SELECT COALESCE(SUM(amount_pence), 0) p FROM ledger_spend WHERE user_id = ?", (uid,)
    ).fetchone()["p"]
    spending = db.execute(
        "SELECT kind, source, counterparty, amount_pence, created_at FROM ledger_spend "
        "WHERE user_id = ? ORDER BY id DESC", (uid,)
    ).fetchall()
    return {
        "user": user,
        "profile": profile,
        "skills": skills,
        "records": records,
        "reviews": reviews,
        "reputation": reputation,
        "review_count": rep["n"],
        "wallet_pence": earned,
        "earnings": earnings,
        "spent_pence": spent,
        "spending": spending,
    }


# --------------------------------------------------------------------------- #
#  Auth — FrameVault is the identity layer, so it owns login. In the full      #
#  ecosystem this same service issues the session every product trusts.        #
# --------------------------------------------------------------------------- #
def current_user():
    uid = session.get("uid")
    return get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone() if uid else None


@app.context_processor
def inject_me():
    """Expose the logged-in user as `me` to every template (drives the nav)."""
    return {"me": current_user()}


def login_required(view):
    @wraps(view)
    def wrapped(*a, **k):
        if not session.get("uid"):
            return redirect(url_for("login", next=request.path))
        return view(*a, **k)
    return wrapped


def api_login_required(view):
    @wraps(view)
    def wrapped(*a, **k):
        if not session.get("uid"):
            return jsonify(ok=False, error="Please log in."), 401
        return view(*a, **k)
    return wrapped


# --------------------------------------------------------------------------- #
#  Pages                                                                       #
# --------------------------------------------------------------------------- #
def own_page():
    """Where a signed-in user lands by default: their own public profile —
    provenance history first, edit control room (/dashboard) is a secondary
    action from there, not the landing state."""
    return redirect(url_for("public_page", handle=current_user()["handle"]))


@app.route("/")
def index():
    return own_page() if session.get("uid") else redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("uid") and request.method == "GET":
        return own_page()
    if request.method == "POST":
        handle = (request.form.get("handle") or "").strip().lstrip("@").lower()
        password = request.form.get("password") or ""
        user = fetch_user(handle=handle)
        if user is None or not check_password_hash(user["password_hash"], password):
            return render_template("login.html", error="Wrong handle or password.", demo=(DEMO_LOGIN if SHOW_DEMO else None)), 401
        session["uid"] = user["id"]
        return redirect(request.args.get("next") or url_for("public_page", handle=user["handle"]))
    return render_template("login.html", demo=(DEMO_LOGIN if SHOW_DEMO else None))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = (request.form.get("display_name") or "").strip()
        handle = (request.form.get("handle") or "").strip().lstrip("@").lower()
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        err = None
        if not name:
            err = "Your name is required."
        elif not HANDLE_RE.match(handle):
            err = "Handle must be 2–20 characters: lowercase letters, numbers, underscore."
        elif len(password) < 6:
            err = "Password must be at least 6 characters."
        elif fetch_user(handle=handle) is not None:
            err = "That handle is already taken."
        if err:
            return render_template("signup.html", error=err, form=request.form), 400
        db = get_db()
        ts = now_iso()
        cur = db.execute(
            "INSERT INTO users (email, display_name, handle, password_hash, verified, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (email or None, name, handle, generate_password_hash(password), 0, ts),
        )
        uid = cur.lastrowid
        db.execute(
            "INSERT INTO creator_profiles (user_id, headline, bio, location, availability, updated_at) "
            "VALUES (?,?,?,?,?,?)",
            (uid, "", "", "", "open", ts),
        )
        db.commit()
        session["uid"] = uid
        # A brand-new profile is empty, so send them straight to the control
        # room to register their first work — own_page() would just show an
        # empty public page with nothing to do yet.
        return redirect(url_for("dashboard"))
    return render_template("signup.html", form={})


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    bundle = profile_bundle(user)
    return render_template("dashboard.html", **bundle)


@app.route("/settings")
@login_required
def settings_page():
    """Profile + skills editing lives here, deliberately apart from
    /dashboard's register-a-work flow — a page you visit on purpose to
    change how you appear, not a form sitting open on a page you pass
    through constantly."""
    user = current_user()
    bundle = profile_bundle(user)
    return render_template("settings.html", **bundle)


@app.route("/@<handle>")
def public_page(handle):
    user = fetch_user(handle=handle.lstrip("@").lower())
    if user is None:
        abort(404)
    bundle = profile_bundle(user)
    return render_template("public.html", is_owner=(session.get("uid") == user["id"]), **bundle)


@app.route("/verify")
def verify_page():
    return render_template("verify.html")


@app.get("/api/creator/<handle>")
def api_creator_public(handle):
    """Public, unauthenticated: just the reputation numbers already visible on
    /@handle, structured as JSON so another product (e.g. RightsForge showing
    a seller's rating next to their listing) can show a trust signal without
    ever seeing anything private like the wallet balance."""
    user = fetch_user(handle=handle.lstrip("@").lower())
    if user is None:
        return jsonify(ok=False, error="No such creator."), 404
    rep = get_db().execute(
        "SELECT AVG(rating) a, COUNT(*) n FROM reviews WHERE subject_user = ?", (user["id"],)
    ).fetchone()
    return jsonify(ok=True, handle=user["handle"], verified=bool(user["verified"]),
                   reputation=round(rep["a"], 1) if rep["a"] is not None else None,
                   review_count=rep["n"])


@app.get("/api/search")
def api_search():
    """Read-only search across creators and registered works, for the command
    palette. Additive endpoint — doesn't touch any existing route."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 1:
        return jsonify(results=[])
    like = f"%{q}%"
    db = get_db()
    results = []
    for u in db.execute(
        "SELECT handle, display_name, verified FROM users WHERE handle LIKE ? OR display_name LIKE ? LIMIT 6",
        (like, like),
    ).fetchall():
        results.append({"type": "Creator", "title": u["display_name"],
                         "subtitle": "@" + u["handle"] + (" · verified" if u["verified"] else ""),
                         "url": f"/@{u['handle']}"})
    for r in db.execute(
        "SELECT p.registry_id, p.title, u.handle FROM provenance_records p JOIN users u ON u.id = p.owner_id "
        "WHERE p.title LIKE ? ORDER BY p.id DESC LIMIT 6",
        (like,),
    ).fetchall():
        results.append({"type": "Work", "title": r["title"], "subtitle": r["registry_id"], "url": f"/@{r['handle']}"})
    return jsonify(results=results)


@app.get("/api/dashboard/stats")
@login_required
def api_dashboard_stats():
    """Read-only snapshot of the signed-in creator's own numbers, for
    client-side polling — the wallet/reputation feel alive as credits land
    from other CreativeOS apps, without a page refresh."""
    user = current_user()
    db = get_db()
    rep = db.execute(
        "SELECT AVG(rating) a, COUNT(*) n FROM reviews WHERE subject_user = ?", (user["id"],)
    ).fetchone()
    records_count = db.execute(
        "SELECT COUNT(*) c FROM provenance_records WHERE owner_id = ?", (user["id"],)
    ).fetchone()["c"]
    earned = db.execute(
        "SELECT COALESCE(SUM(amount_pence), 0) p FROM reputation_events WHERE user_id = ?", (user["id"],)
    ).fetchone()["p"]
    return jsonify(
        reputation=round(rep["a"], 1) if rep["a"] is not None else None,
        review_count=rep["n"], records=records_count, earned_pence=earned,
    )


@app.get("/__whoami")
def whoami():
    """Identity probe for scripts/check_ports.py — a port can be identified, not guessed."""
    return jsonify(app="FrameVault", track="CreativeOS", role="identity + provenance", port=PORT)


# --------------------------------------------------------------------------- #
#  JSON API                                                                    #
# --------------------------------------------------------------------------- #
@app.post("/api/profile")
@api_login_required
def api_profile():
    uid = session["uid"]
    data = request.get_json(force=True)
    db = get_db()
    db.execute(
        "UPDATE creator_profiles SET headline=?, bio=?, location=?, availability=?, updated_at=? "
        "WHERE user_id=?",
        (
            data.get("headline", "").strip(),
            data.get("bio", "").strip(),
            data.get("location", "").strip(),
            data.get("availability", "open").strip(),
            now_iso(),
            uid,
        ),
    )
    db.commit()
    return jsonify(ok=True)


@app.post("/api/skills")
@api_login_required
def api_add_skill():
    uid = session["uid"]
    data = request.get_json(force=True)
    skill = (data.get("skill") or "").strip()
    level = (data.get("level") or "Intermediate").strip()
    if not skill:
        return jsonify(ok=False, error="Skill name is required."), 400
    db = get_db()
    cur = db.execute(
        "INSERT INTO profile_skills (user_id, skill, level) VALUES (?,?,?)",
        (uid, skill, level),
    )
    db.commit()
    return jsonify(ok=True, id=cur.lastrowid, skill=skill, level=level)


@app.delete("/api/skills/<int:skill_id>")
@api_login_required
def api_delete_skill(skill_id):
    uid = session["uid"]
    db = get_db()
    db.execute(
        "DELETE FROM profile_skills WHERE id=? AND user_id=?", (skill_id, uid)
    )
    db.commit()
    return jsonify(ok=True)


@app.post("/api/provenance")
@api_login_required
def api_register():
    """Register a work: store the client-computed hash + metadata, sign it, return the receipt."""
    uid = session["uid"]
    data = request.get_json(force=True)
    content_hash = (data.get("content_hash") or "").strip().lower()
    title = (data.get("title") or "").strip()

    if not HASH_RE.match(content_hash):
        return jsonify(ok=False, error="A valid SHA-256 hash is required."), 400
    if not title:
        return jsonify(ok=False, error="A title is required."), 400

    db = get_db()
    # Prevent a creator from registering the exact same file twice.
    dup = db.execute(
        "SELECT registry_id FROM provenance_records WHERE owner_id=? AND content_hash=?",
        (uid, content_hash),
    ).fetchone()
    if dup:
        return jsonify(
            ok=False,
            error=f"You have already registered this exact file ({dup['registry_id']}).",
        ), 409

    rid = new_registry_id()
    created = now_iso()
    role = (data.get("role") or "").strip()
    contributors = (data.get("contributors") or "").strip()
    ai_disclosure = (data.get("ai_disclosure") or "").strip()
    rec = {
        "content_hash": content_hash, "registry_id": rid, "owner_id": uid,
        "created_at": created, "title": title, "role": role,
        "contributors": contributors, "ai_disclosure": ai_disclosure, "source": "FrameVault",
    }
    signature = sign(rec)
    # FILE-STORAGE SEAM: today we store hash-only (filename/mime/bytes are metadata; the file itself
    # never leaves the browser). To optionally host files later, this is where we'd stream the upload
    # to object storage (e.g. S3) and save its key here — no schema change beyond one column.
    db.execute(
        "INSERT INTO provenance_records "
        "(registry_id, owner_id, content_hash, filename, mime, bytes, title, role, "
        " contributors, ai_disclosure, source, created_at, signature) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            rid, uid, content_hash,
            (data.get("filename") or "").strip(),
            (data.get("mime") or "").strip(),
            int(data.get("bytes") or 0),
            title, role, contributors, ai_disclosure,
            "FrameVault",
            created,
            signature,
        ),
    )
    db.execute(
        "INSERT INTO reputation_events (user_id, kind, weight, source, created_at) "
        "VALUES (?,?,?,?,?)",
        (uid, "work.registered", 1, "FrameVault", created),
    )
    db.commit()
    return jsonify(
        ok=True,
        record={
            "registry_id": rid,
            "content_hash": content_hash,
            "title": title,
            "role": role,
            "contributors": contributors,
            "ai_disclosure": ai_disclosure,
            "created_at": created,
            "signature": signature,
        },
    )


@app.post("/api/verify")
def api_verify():
    """Public: given a SHA-256 hash, report whether it is registered and to whom."""
    data = request.get_json(force=True)
    content_hash = (data.get("content_hash") or "").strip().lower()
    if not HASH_RE.match(content_hash):
        return jsonify(ok=False, error="Paste a valid SHA-256 hash, or drop the file to hash it."), 400

    db = get_db()
    row = db.execute(
        "SELECT p.*, u.display_name, u.handle, u.verified "
        "FROM provenance_records p JOIN users u ON u.id = p.owner_id "
        "WHERE p.content_hash = ? ORDER BY p.id ASC LIMIT 1",
        (content_hash,),
    ).fetchone()

    if row is None:
        return jsonify(ok=True, registered=False, content_hash=content_hash)

    signature_valid = hmac.compare_digest(row["signature"], sign(row))
    return jsonify(
        ok=True,
        registered=True,
        content_hash=content_hash,
        record={
            "registry_id": row["registry_id"],
            "title": row["title"],
            "role": row["role"],
            "contributors": row["contributors"],
            "ai_disclosure": row["ai_disclosure"],
            "owner_name": row["display_name"],
            "owner_handle": row["handle"],
            "owner_verified": bool(row["verified"]),
            "created_at": row["created_at"],
            "signature": row["signature"],
            "signature_valid": signature_valid,
        },
    )


@app.post("/api/credit")
def api_credit():
    """
    Service-to-service (THE EVENT SEAM): another CreativeOS product records a verified
    credit on a creator's FrameVault — e.g. FilmCrew posts here when a hire completes.
    Authenticated by a shared service key, NOT a user session. This is how a hire in one
    product makes a creator's identity richer in another, without the products sharing a
    database. In the full build this arrives via the event bus; the contract is identical.
    """
    if not hmac.compare_digest(request.headers.get("X-Service-Key", ""), SERVICE_KEY):
        return jsonify(ok=False, error="Unauthorized service."), 401
    data = request.get_json(force=True)
    handle = (data.get("handle") or "").strip().lstrip("@").lower()
    user = fetch_user(handle=handle)
    if user is None:
        return jsonify(ok=False, error="No FrameVault creator with that handle."), 404

    kind = (data.get("kind") or "hire.completed").strip()
    source = (data.get("source") or "FilmCrew").strip()
    weight = float(data.get("weight") or 5)
    # Amount arrives in pounds (matching how every product already displays
    # money, e.g. "£1,200"); stored as integer pence so summing many rows
    # never drifts from float rounding. 0 when the credited action wasn't a
    # paid transaction (OTT Studio's project.published, Story Atlas's
    # canon.published) — the wallet only ever reflects real money.
    amount_pence = round(float(data.get("amount") or 0) * 100)
    created = now_iso()
    db = get_db()
    db.execute(
        "INSERT INTO reputation_events (user_id, kind, weight, source, amount_pence, created_at) VALUES (?,?,?,?,?,?)",
        (user["id"], kind, weight, source, amount_pence, created),
    )
    review = data.get("review")
    if review:
        db.execute(
            "INSERT INTO reviews (subject_user, author_name, author_handle, rating, body, context, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (user["id"], (review.get("author_name") or "Producer").strip(),
             (review.get("author_handle") or "").strip(), int(review.get("rating") or 5),
             (review.get("body") or "").strip(),
             (review.get("context") or f"via {source}").strip(), created),
        )
    # The payer's side of the same transaction — the calling product tells us
    # who paid, we write the matching spend leg, so the ledger has both parties
    # instead of only ever proving the earner's half.
    spend_recorded = False
    payer_handle = (data.get("payer_handle") or "").strip().lstrip("@").lower()
    if payer_handle and amount_pence > 0:
        payer = fetch_user(handle=payer_handle)
        if payer is not None:
            db.execute(
                "INSERT INTO ledger_spend (user_id, counterparty, kind, source, amount_pence, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (payer["id"], handle, kind, source, amount_pence, created),
            )
            spend_recorded = True
    db.commit()
    return jsonify(ok=True, handle=handle, credited=kind, public_url=f"/@{handle}", spend_recorded=spend_recorded)


@app.post("/api/authenticate")
def api_authenticate():
    """
    Service-to-service SHARED IDENTITY ("one login"): another CreativeOS product verifies a
    creator's FrameVault credentials, so a person has ONE account across the whole ecosystem.
    The calling product forwards the password once and never stores it — it receives only the
    identity back. FrameVault stays the single source of truth for who someone is, which is
    exactly why identity was the first product built.
    """
    if not hmac.compare_digest(request.headers.get("X-Service-Key", ""), SERVICE_KEY):
        return jsonify(ok=False, error="Unauthorized service."), 401
    data = request.get_json(force=True)
    handle = (data.get("handle") or "").strip().lstrip("@").lower()
    password = data.get("password") or ""
    user = fetch_user(handle=handle)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify(ok=False, error="Wrong handle or password."), 401
    return jsonify(ok=True, user={
        "id": user["id"],
        "handle": user["handle"],
        "display_name": user["display_name"],
        "verified": bool(user["verified"]),
    })


@app.errorhandler(404)
def not_found(_e):
    return render_template("verify.html", not_found=True), 404


# Ensure tables exist at import time too, so a production WSGI server (gunicorn), which
# never runs the __main__ block, still has a ready database.
init_db()

if __name__ == "__main__":
    # Port registered in /PORTS.md; override with FRAMEVAULT_PORT if you need a scratch instance.
    # HOST defaults to loopback-only; set HOST=0.0.0.0 (see scripts/run_for_phone.py) to reach
    # this from another device on the same network, e.g. a phone.
    app.run(debug=True, host=os.environ.get("HOST", "127.0.0.1"), port=PORT)
