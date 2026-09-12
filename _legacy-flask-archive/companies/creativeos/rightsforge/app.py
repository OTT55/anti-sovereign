"""
RightsForge — the rights marketplace of CreativeOS (working name).

Originally planned as two separate products, RightsHub (asset licensing) and StoryForge
(IP marketplace). They turned out to be the same engine wearing two hats: a creator lists
creative work, a buyer acquires rights to it, money moves, and provenance/ownership matters.
Building that engine twice would mean maintaining two copies of the same marketplace. So this
is ONE app with a `listing_type` that branches the deal flow:

  * "asset"  — music, SFX, LUTs, VFX, templates, motion, voice, footage.
               Non-exclusive, instant license, many buyers, small price, high volume.
               Optional royalty split across contributors.
  * "ip"     — scripts, novels, comics, pilots, game concepts.
               Usually exclusive, negotiated: option -> license -> purchase, one buyer,
               large price, low volume. Advances through a short deal flow, not instant.

Same listings table, same seller identity, same payments concept, same "who owns this" —
only the deal shape and the fields shown differ.

Two seams to FrameVault (same pattern as FilmCrew — see its app.py for the reasoning):
  1. IDENTITY — /api/authenticate: one login across CreativeOS ("one login, many apps,
               exactly like Google"). RightsForge never stores a password.
  2. CREDIT   — /api/credit: a completed deal enriches the seller's FrameVault. Asset
               licenses fire `asset.licensed`; IP deals fire `ip.optioned` / `ip.licensed` /
               `ip.purchased` depending on the deal kind — matching docs/database-schema.md
               and docs/api-design.md's event names.

Isolation (per companies/creativeos/framevault/ARCHITECTURE.md):
  * Own folder, own database (rightsforge.db), own port (5003, see /PORTS.md).
  * RightsForge NEVER touches FrameVault's or FilmCrew's database.

Run:  python app.py   ->  http://127.0.0.1:5003   (FrameVault should be running on 5001)
"""

import hashlib
import os
import json
import sqlite3
import datetime
import urllib.request
import urllib.error
import uuid
from functools import wraps

from flask import (
    Flask, request, jsonify, render_template, redirect, url_for, abort, g, session,
    send_from_directory,
)
from werkzeug.utils import secure_filename

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("RF_DB", os.path.join(APP_DIR, "rightsforge.db"))
# Local disk today; swap save_upload() for a Supabase storage client later
# without touching any route. Gated behind ownership/purchase — see
# api_download_listing() — unlike Studio's assets, this is a marketplace:
# the raw file is the thing being sold, not something to hand out for free.
UPLOAD_DIR = os.path.join(APP_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200MB — real audio/video/LUT packs, not placeholders

# Port comes from the environment so you never edit code to move it.
# Registered in /PORTS.md — CreativeOS owns the 5000–5099 block; RightsForge is 5003.
PORT = int(os.environ.get("RIGHTSFORGE_PORT", 5003))

# Where FrameVault lives, and the shared key it trusts (must match FrameVault's FV_SERVICE_KEY).
FRAMEVAULT_URL = os.environ.get("FRAMEVAULT_URL", "http://127.0.0.1:5001")
SERVICE_KEY = os.environ.get("FV_SERVICE_KEY", "creativeos-dev-service-key")

app = Flask(__name__)
# Session cookie secret. RightsForge stores only *who you are*, never your password.
app.secret_key = os.environ.get("RF_SECRET", "rightsforge-dev-secret-change-in-production")

ASSET_CATEGORIES = ["music", "sfx", "lut", "vfx", "template", "motion", "voice", "footage"]
IP_FORMATS = ["script", "novel", "comic", "pilot", "game_concept", "idea"]
IP_KINDS = ["option", "license", "purchase"]     # what an IP deal can be
IP_FLOW = ["proposed", "agreed", "paid"]          # a deal walks these in order


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def save_upload(file_storage):
    """Save an uploaded file to local disk and hash it. Returns
    (stored_name, filename, mime, bytes, sha256_hex) or all-empty/0 if no
    file was given. The hash is shown publicly on the listing regardless of
    who can download the file — it's how a buyer verifies what they actually
    received matches what was listed, tamper-evident either way."""
    if not file_storage or not file_storage.filename:
        return None, "", "", 0, ""
    safe = secure_filename(file_storage.filename) or "upload"
    stored_name = f"{uuid.uuid4().hex}_{safe}"
    dest = os.path.join(UPLOAD_DIR, stored_name)
    file_storage.save(dest)
    size = os.path.getsize(dest)
    if size > MAX_UPLOAD_BYTES:
        os.remove(dest)
        raise ValueError(f"File too large ({size // (1024*1024)}MB) — max {MAX_UPLOAD_BYTES // (1024*1024)}MB.")
    hasher = hashlib.sha256()
    with open(dest, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            hasher.update(chunk)
    return stored_name, file_storage.filename, (file_storage.mimetype or ""), size, hasher.hexdigest()


# --------------------------------------------------------------------------- #
#  Database (own store — never shared with FrameVault or FilmCrew)            #
# --------------------------------------------------------------------------- #
SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  listing_type  TEXT NOT NULL,             -- 'asset' | 'ip'
  seller_handle TEXT NOT NULL,             -- FrameVault @handle of the seller
  seller_name   TEXT NOT NULL,
  title         TEXT NOT NULL,
  category      TEXT DEFAULT '',           -- asset: category; ip: format
  description   TEXT DEFAULT '',
  provenance_id TEXT DEFAULT '',           -- optional FrameVault registry_id for this work
  status        TEXT DEFAULT 'listed',     -- listed | optioned | sold (ip only; assets stay 'listed')
  stored_name   TEXT DEFAULT '',           -- filename on disk under static/uploads/, '' = no file attached
  filename      TEXT DEFAULT '',           -- original filename, for display/download
  mime          TEXT DEFAULT '',
  bytes         INTEGER DEFAULT 0,
  content_hash  TEXT DEFAULT '',           -- SHA-256 of the uploaded file — shown publicly so a buyer
                                            -- can verify what they received matches what was listed
  created_at    TEXT NOT NULL
);
-- Asset license tiers, e.g. Personal / Commercial / Studio.
CREATE TABLE IF NOT EXISTS asset_tiers (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  listing_id INTEGER NOT NULL REFERENCES listings(id),
  name       TEXT NOT NULL,
  price      INTEGER NOT NULL
);
-- Optional royalty split across contributors on an asset (paid on every license).
CREATE TABLE IF NOT EXISTS royalty_splits (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  listing_id  INTEGER NOT NULL REFERENCES listings(id),
  payee_name  TEXT NOT NULL,
  payee_pct   INTEGER NOT NULL
);
-- IP deal terms, e.g. Option £4,000 / License £18,000 / Buyout £45,000.
CREATE TABLE IF NOT EXISTS ip_terms (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  listing_id INTEGER NOT NULL REFERENCES listings(id),
  kind       TEXT NOT NULL,               -- option | license | purchase
  price      INTEGER NOT NULL
);
-- Every completed transaction: instant for assets, a short flow for IP.
CREATE TABLE IF NOT EXISTS deals (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  listing_id   INTEGER NOT NULL REFERENCES listings(id),
  buyer_handle TEXT NOT NULL,
  buyer_name   TEXT NOT NULL,
  kind         TEXT NOT NULL,             -- asset: tier name; ip: option|license|purchase
  price        INTEGER NOT NULL,
  status       TEXT DEFAULT 'paid',       -- asset: always 'paid' (instant); ip: proposed|agreed|paid
  credited     INTEGER NOT NULL DEFAULT 0,
  credit_note  TEXT DEFAULT '',
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
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
    exists from an older version of SCHEMA — the upload columns postdate the
    original listings table. Add them if missing."""
    cols = {row[1] for row in db.execute("PRAGMA table_info(listings)")}
    for col, decl in (("stored_name", "TEXT DEFAULT ''"), ("filename", "TEXT DEFAULT ''"),
                       ("mime", "TEXT DEFAULT ''"), ("bytes", "INTEGER DEFAULT 0"),
                       ("content_hash", "TEXT DEFAULT ''")):
        if col not in cols:
            db.execute(f"ALTER TABLE listings ADD COLUMN {col} {decl}")


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    _migrate(db)
    if db.execute("SELECT COUNT(*) FROM listings").fetchone()[0] == 0:
        seed(db)
    db.commit()
    db.close()


def seed(db):
    ts = now_iso()

    # --- Asset: OTT's "Umber" LUT pack, a real FrameVault seller, with a royalty split ---
    lid = db.execute(
        "INSERT INTO listings (listing_type, seller_handle, seller_name, title, category, "
        "description, status, created_at) VALUES ('asset',?,?,?,?,?,?,?)",
        ("ott", "OTT", "“Umber” — warm cinematic LUT pack", "lut",
         "Ten hand-built color grades tuned for skin tones in low, practical light — the same "
         "looks OTT used on “Nightshift”. Tested across Log profiles from major camera systems.",
         "listed", ts),
    ).lastrowid
    for name, price in [("Personal / royalty-free", 29), ("Commercial", 89), ("Studio (unlimited seats)", 240)]:
        db.execute("INSERT INTO asset_tiers (listing_id, name, price) VALUES (?,?,?)", (lid, name, price))
    for payee, pct in [("OTT", 70), ("Kojo Mensah", 30)]:
        db.execute("INSERT INTO royalty_splits (listing_id, payee_name, payee_pct) VALUES (?,?,?)",
                   (lid, payee, pct))

    # --- Asset: a music bed from a non-FrameVault seller ---
    lid2 = db.execute(
        "INSERT INTO listings (listing_type, seller_handle, seller_name, title, category, "
        "description, status, created_at) VALUES ('asset','','Nova',?,?,?,?,?)",
        ("“Low Tide” — ambient bed", "music",
         "Cinematic, loopable ambient bed. 2:41. Clean stems included.", "listed", ts),
    ).lastrowid
    for name, price in [("Royalty-free", 39), ("Commercial", 99)]:
        db.execute("INSERT INTO asset_tiers (listing_id, name, price) VALUES (?,?,?)", (lid2, name, price))

    # --- IP: OTT's "The Archivist" pilot, a real FrameVault seller ---
    lid3 = db.execute(
        "INSERT INTO listings (listing_type, seller_handle, seller_name, title, category, "
        "description, status, created_at) VALUES ('ip',?,?,?,?,?,?,?)",
        ("ott", "OTT", "“The Archivist”", "pilot",
         "In a city that has outlawed forgetting, a state archivist discovers a memory that was "
         "never meant to be recorded — and that someone is willing to erase her to bury it. A "
         "tense, world-heavy pilot about who controls the past.",
         "listed", ts),
    ).lastrowid
    for kind, price in [("option", 4000), ("license", 18000), ("purchase", 45000)]:
        db.execute("INSERT INTO ip_terms (listing_id, kind, price) VALUES (?,?,?)", (lid3, kind, price))

    # --- IP: a non-FrameVault seller's feature script ---
    lid4 = db.execute(
        "INSERT INTO listings (listing_type, seller_handle, seller_name, title, category, "
        "description, status, created_at) VALUES ('ip','','Elin F.',?,?,?,?,?)",
        ("“Saltwater”", "script",
         "Drama. A diver returns to a drowned town to find out what really happened the night it flooded.",
         "listed", ts),
    ).lastrowid
    for kind, price in [("option", 3000), ("purchase", 32000)]:
        db.execute("INSERT INTO ip_terms (listing_id, kind, price) VALUES (?,?,?)", (lid4, kind, price))


# --------------------------------------------------------------------------- #
#  Cross-service calls — the seams to FrameVault                              #
# --------------------------------------------------------------------------- #
def framevault_post(path, payload, timeout=5):
    """POST JSON to FrameVault with the shared service key. Returns (ok, data)."""
    req = urllib.request.Request(
        f"{FRAMEVAULT_URL}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Service-Key": SERVICE_KEY},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return False, json.loads(e.read().decode())
        except Exception:
            return False, {"error": f"FrameVault returned {e.code}."}
    except urllib.error.URLError:
        return False, {"error": "Couldn't reach FrameVault — is it running on port 5001?"}


def seller_rating(handle, timeout=2):
    """A seller's public FrameVault rating — not their earnings, which stay
    private to them. None if they're not on FrameVault or it's unreachable;
    the template shows nothing rather than a fake number."""
    if not handle:
        return None
    try:
        with urllib.request.urlopen(f"{FRAMEVAULT_URL}/api/creator/{handle}", timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            return data if data.get("ok") else None
    except Exception:
        return None


def credit_framevault(seller_handle, kind, weight, body, context, amount=0, payer_handle=""):
    """THE MAGIC MOMENT: a completed deal becomes verified earnings history on the seller's FrameVault.

    payer_handle (the buyer) lets FrameVault write the other half of the same
    transaction — a real ledger entry on the buyer's side, not just the seller's."""
    return framevault_post("/api/credit", {
        "handle": seller_handle,
        "payer_handle": payer_handle,
        "kind": kind,
        "source": "RightsForge",
        "weight": weight,
        "amount": amount,
        "review": {"author_name": "RightsForge buyer", "rating": 5, "body": body, "context": context},
    })


# --------------------------------------------------------------------------- #
#  Auth — one login, borrowed from FrameVault (the identity seam)             #
# --------------------------------------------------------------------------- #
def current_user():
    if "handle" not in session:
        return None
    return {"handle": session["handle"], "name": session.get("name", session["handle"]),
            "verified": session.get("verified", False)}


@app.context_processor
def inject_me():
    return {"me": current_user(), "framevault_url": FRAMEVAULT_URL}


def login_required(view):
    @wraps(view)
    def wrapped(*a, **k):
        if "handle" not in session:
            return redirect(url_for("login", next=request.path))
        return view(*a, **k)
    return wrapped


def api_login_required(view):
    @wraps(view)
    def wrapped(*a, **k):
        if "handle" not in session:
            return jsonify(ok=False, error="Please log in with your FrameVault account."), 401
        return view(*a, **k)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        handle = (request.form.get("handle") or "").strip().lstrip("@").lower()
        password = request.form.get("password") or ""
        ok, data = framevault_post("/api/authenticate", {"handle": handle, "password": password})
        if not ok:
            return render_template("login.html", error=data.get("error", "Login failed.")), 401
        u = data["user"]
        session["handle"] = u["handle"]
        session["name"] = u["display_name"]
        session["verified"] = u["verified"]
        return redirect(request.args.get("next") or url_for("marketplace"))
    if "handle" in session:
        return redirect(url_for("marketplace"))
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --------------------------------------------------------------------------- #
#  Pages                                                                       #
# --------------------------------------------------------------------------- #
def listing_extra(db, listing):
    """Attach tiers/terms/splits depending on listing_type."""
    d = dict(listing)
    if listing["listing_type"] == "asset":
        d["tiers"] = db.execute(
            "SELECT * FROM asset_tiers WHERE listing_id=? ORDER BY price", (listing["id"],)
        ).fetchall()
        d["splits"] = db.execute(
            "SELECT * FROM royalty_splits WHERE listing_id=?", (listing["id"],)
        ).fetchall()
        d["license_count"] = db.execute(
            "SELECT COUNT(*) c FROM deals WHERE listing_id=?", (listing["id"],)
        ).fetchone()["c"]
    else:
        d["terms"] = db.execute(
            "SELECT * FROM ip_terms WHERE listing_id=? ORDER BY price", (listing["id"],)
        ).fetchall()
        d["deal"] = db.execute(
            "SELECT * FROM deals WHERE listing_id=? ORDER BY id DESC LIMIT 1", (listing["id"],)
        ).fetchone()
    return d


@app.route("/")
def marketplace():
    db = get_db()
    mode = request.args.get("mode", "asset")
    cat = request.args.get("cat", "")
    if mode == "ip":
        rows = db.execute(
            "SELECT * FROM listings WHERE listing_type='ip'" + (" AND category=?" if cat else "") +
            " ORDER BY id DESC", ((cat,) if cat else ())
        ).fetchall()
        cats = IP_FORMATS
    else:
        mode = "asset"
        rows = db.execute(
            "SELECT * FROM listings WHERE listing_type='asset'" + (" AND category=?" if cat else "") +
            " ORDER BY id DESC", ((cat,) if cat else ())
        ).fetchall()
        cats = ASSET_CATEGORIES
    listings = [listing_extra(db, r) for r in rows]
    stats = {
        "assets": db.execute("SELECT COUNT(*) c FROM listings WHERE listing_type='asset'").fetchone()["c"],
        "ip": db.execute("SELECT COUNT(*) c FROM listings WHERE listing_type='ip'").fetchone()["c"],
        "deals": db.execute("SELECT COUNT(*) c FROM deals").fetchone()["c"],
    }
    return render_template("marketplace.html", mode=mode, cat=cat, cats=cats, listings=listings,
                           stats=stats)


def can_download(db, handle, listing):
    """The file is what's being sold, so it's gated: the seller can always see
    it, and a buyer only after they've actually paid — never a visitor who
    just landed on the listing page."""
    if not listing.get("stored_name") or not handle:
        return False
    if handle == listing.get("seller_handle"):
        return True
    return db.execute(
        "SELECT 1 FROM deals WHERE listing_id=? AND buyer_handle=? AND status='paid' LIMIT 1",
        (listing["id"], handle),
    ).fetchone() is not None


@app.route("/listing/<int:lid>")
def listing_page(lid):
    db = get_db()
    row = db.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone()
    if row is None:
        abort(404)
    listing = listing_extra(db, row)
    me = current_user()
    return render_template("listing.html", l=listing, flow=IP_FLOW,
                           rating=seller_rating(listing.get("seller_handle")),
                           can_dl=can_download(db, me["handle"] if me else None, listing))


@app.get("/api/listing/<int:lid>/download")
@login_required
def download_listing_file(lid):
    db = get_db()
    row = db.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone()
    if row is None or not row["stored_name"]:
        abort(404)
    me = current_user()
    if not can_download(db, me["handle"], dict(row)):
        abort(403)
    return send_from_directory(UPLOAD_DIR, row["stored_name"], as_attachment=True,
                                download_name=row["filename"] or row["stored_name"])


@app.route("/sell")
@login_required
def sell_page():
    return render_template("sell.html", asset_cats=ASSET_CATEGORIES, ip_formats=IP_FORMATS)


@app.route("/mine")
@login_required
def mine_page():
    db = get_db()
    me = current_user()
    selling = [listing_extra(db, r) for r in db.execute(
        "SELECT * FROM listings WHERE seller_handle=? ORDER BY id DESC", (me["handle"],)
    ).fetchall()]
    buying = db.execute(
        "SELECT d.*, l.title, l.listing_type FROM deals d JOIN listings l ON l.id=d.listing_id "
        "WHERE d.buyer_handle=? ORDER BY d.id DESC", (me["handle"],)
    ).fetchall()
    earned = db.execute(
        "SELECT COALESCE(SUM(d.price),0) s FROM deals d JOIN listings l ON l.id=d.listing_id "
        "WHERE l.seller_handle=? AND d.status='paid'", (me["handle"],)
    ).fetchone()["s"]
    return render_template("mine.html", selling=selling, buying=buying, earned=earned)


# --------------------------------------------------------------------------- #
#  JSON API                                                                    #
# --------------------------------------------------------------------------- #
@app.post("/api/listing")
@api_login_required
def api_create_listing():
    d = request.form
    me = current_user()
    ltype = (d.get("listing_type") or "").strip()
    title = (d.get("title") or "").strip()
    if ltype not in ("asset", "ip"):
        return jsonify(ok=False, error="listing_type must be 'asset' or 'ip'."), 400
    if not title:
        return jsonify(ok=False, error="A title is required."), 400

    try:
        stored_name, filename, mime, size, content_hash = save_upload(request.files.get("file"))
    except ValueError as e:
        return jsonify(ok=False, error=str(e)), 400

    db = get_db()
    lid = db.execute(
        "INSERT INTO listings (listing_type, seller_handle, seller_name, title, category, "
        "description, provenance_id, status, stored_name, filename, mime, bytes, content_hash, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (ltype, me["handle"], me["name"], title, (d.get("category") or "").strip(),
         (d.get("description") or "").strip(), (d.get("provenance_id") or "").strip(),
         "listed", stored_name or "", filename, mime, size, content_hash, now_iso()),
    ).lastrowid

    if ltype == "asset":
        tiers = json.loads(d.get("tiers_json") or "[]")
        for t in tiers:
            name = (t.get("name") or "").strip()
            price = int(t.get("price") or 0)
            if name and price > 0:
                db.execute("INSERT INTO asset_tiers (listing_id, name, price) VALUES (?,?,?)",
                          (lid, name, price))
        if not tiers:
            db.execute("INSERT INTO asset_tiers (listing_id, name, price) VALUES (?,?,?)",
                      (lid, "Standard license", int(d.get("price") or 29)))
    else:
        terms = json.loads(d.get("terms_json") or "[]")
        for t in terms:
            kind = (t.get("kind") or "").strip()
            price = int(t.get("price") or 0)
            if kind in IP_KINDS and price > 0:
                db.execute("INSERT INTO ip_terms (listing_id, kind, price) VALUES (?,?,?)",
                          (lid, kind, price))
        if not terms:
            db.execute("INSERT INTO ip_terms (listing_id, kind, price) VALUES (?,?,?)",
                      (lid, "option", int(d.get("price") or 1000)))

    db.commit()
    return jsonify(ok=True, id=lid)


@app.post("/api/listing/<int:lid>/license")
@api_login_required
def api_license_asset(lid):
    """Instant purchase of an asset license — the deal is 'paid' the moment it's made."""
    me = current_user()
    tier_id = request.get_json(force=True).get("tier_id")
    db = get_db()
    listing = db.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone()
    tier = db.execute("SELECT * FROM asset_tiers WHERE id=? AND listing_id=?", (tier_id, lid)).fetchone()
    if listing is None or tier is None or listing["listing_type"] != "asset":
        return jsonify(ok=False, error="Unknown listing or tier."), 404
    if listing["seller_handle"] == me["handle"]:
        return jsonify(ok=False, error="You can't license your own asset."), 400

    ts = now_iso()
    did = db.execute(
        "INSERT INTO deals (listing_id, buyer_handle, buyer_name, kind, price, status, "
        "created_at, updated_at) VALUES (?,?,?,?,?,'paid',?,?)",
        (lid, me["handle"], me["name"], tier["name"], tier["price"], ts, ts),
    ).lastrowid
    db.commit()

    resp = {"ok": True, "deal_id": did, "status": "paid", "credited": False}
    # Credit the SELLER, split across any royalty holders — only the FrameVault-registered ones.
    if listing["seller_handle"]:
        ok, detail = credit_framevault(
            listing["seller_handle"], "asset.licensed", 3,
            f"“{listing['title']}” licensed — {tier['name']} £{tier['price']}.",
            f"Licensed by @{me['handle']} · via RightsForge",
            amount=tier["price"], payer_handle=me["handle"],
        )
        note = "Credit written to FrameVault." if ok else f"FrameVault not updated: {detail.get('error','error')}"
        db.execute("UPDATE deals SET credited=?, credit_note=? WHERE id=?", (1 if ok else 0, note, did))
        resp.update(credited=ok, note=note, public_url=f"{FRAMEVAULT_URL}/@{listing['seller_handle']}")
    else:
        note = "Paid. The seller isn't on FrameVault yet, so no credit was written."
        db.execute("UPDATE deals SET credit_note=? WHERE id=?", (note, did))
        resp.update(note=note)
    db.commit()
    return jsonify(resp)


@app.post("/api/listing/<int:lid>/deal")
@api_login_required
def api_start_ip_deal(lid):
    """Start an IP deal — creates it at step 1 ('proposed'). No credit yet."""
    me = current_user()
    d = request.get_json(force=True)
    kind = (d.get("kind") or "").strip()
    db = get_db()
    listing = db.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone()
    term = db.execute("SELECT * FROM ip_terms WHERE listing_id=? AND kind=?", (lid, kind)).fetchone()
    if listing is None or term is None or listing["listing_type"] != "ip":
        return jsonify(ok=False, error="Unknown listing or deal kind."), 404
    if listing["seller_handle"] == me["handle"]:
        return jsonify(ok=False, error="You can't deal on your own IP."), 400
    if listing["status"] != "listed":
        return jsonify(ok=False, error="This IP already has a deal in progress or is no longer available."), 409

    ts = now_iso()
    did = db.execute(
        "INSERT INTO deals (listing_id, buyer_handle, buyer_name, kind, price, status, "
        "created_at, updated_at) VALUES (?,?,?,?,?,'proposed',?,?)",
        (lid, me["handle"], me["name"], kind, term["price"], ts, ts),
    ).lastrowid
    db.commit()
    return jsonify(ok=True, deal_id=did, status="proposed")


@app.post("/api/deal/<int:did>/advance")
@api_login_required
def api_advance_deal(did):
    """
    Move an IP deal one step: proposed -> agreed -> paid.
    Reaching PAID is what fires the FrameVault credit and locks the listing
    (an option/license/purchase means the IP is no longer freely available).
    """
    db = get_db()
    deal = db.execute("SELECT * FROM deals WHERE id=?", (did,)).fetchone()
    if deal is None:
        return jsonify(ok=False, error="Unknown deal."), 404
    if deal["status"] == "paid":
        return jsonify(ok=False, error="This deal is already complete."), 409

    nxt = IP_FLOW[IP_FLOW.index(deal["status"]) + 1]
    ts = now_iso()
    db.execute("UPDATE deals SET status=?, updated_at=? WHERE id=?", (nxt, ts, did))

    listing = db.execute("SELECT * FROM listings WHERE id=?", (deal["listing_id"],)).fetchone()
    resp = {"ok": True, "status": nxt, "credited": False}

    if nxt == "paid":
        new_status = "sold" if deal["kind"] == "purchase" else "optioned"
        db.execute("UPDATE listings SET status=? WHERE id=?", (new_status, listing["id"]))

        event_kind = {"option": "ip.optioned", "license": "ip.licensed", "purchase": "ip.purchased"}[deal["kind"]]
        if listing["seller_handle"]:
            ok, detail = credit_framevault(
                listing["seller_handle"], event_kind, 4,
                f"“{listing['title']}” {deal['kind']}ed for £{deal['price']:,} — escrow released.",
                f"{deal['kind'].capitalize()}ed by @{deal['buyer_handle']} · via RightsForge",
                amount=deal["price"], payer_handle=deal["buyer_handle"],
            )
            note = "Credit written to FrameVault." if ok else f"FrameVault not updated: {detail.get('error','error')}"
            db.execute("UPDATE deals SET credited=?, credit_note=? WHERE id=?", (1 if ok else 0, note, did))
            resp.update(credited=ok, note=note, public_url=f"{FRAMEVAULT_URL}/@{listing['seller_handle']}")
        else:
            note = "Paid. The seller isn't on FrameVault yet, so no credit was written."
            db.execute("UPDATE deals SET credit_note=? WHERE id=?", (note, did))
            resp.update(note=note)

    db.commit()
    return jsonify(resp)


@app.get("/api/marketplace/stats")
def api_marketplace_stats():
    """Read-only snapshot of the marketplace's header stats, for client-side
    polling — same query as marketplace(). Additive, changes nothing."""
    db = get_db()
    return jsonify(
        assets=db.execute("SELECT COUNT(*) c FROM listings WHERE listing_type='asset'").fetchone()["c"],
        ip=db.execute("SELECT COUNT(*) c FROM listings WHERE listing_type='ip'").fetchone()["c"],
        deals=db.execute("SELECT COUNT(*) c FROM deals").fetchone()["c"],
    )


@app.get("/api/search")
def api_search():
    """Read-only search across listings, for the command palette. Additive
    endpoint — doesn't touch any existing route."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 1:
        return jsonify(results=[])
    like = f"%{q}%"
    db = get_db()
    results = []
    for l in db.execute(
        "SELECT id, title, listing_type, category FROM listings WHERE status='listed' "
        "AND (title LIKE ? OR description LIKE ?) ORDER BY id DESC LIMIT 8",
        (like, like),
    ).fetchall():
        kind = "Asset" if l["listing_type"] == "asset" else "IP"
        results.append({"type": kind, "title": l["title"], "subtitle": (l["category"] or "").replace("_", " "),
                         "url": f"/listing/{l['id']}"})
    return jsonify(results=results)


@app.get("/__whoami")
def whoami():
    """Identity probe for scripts/check_ports.py — a port can be identified, not guessed."""
    return jsonify(app="RightsForge", track="CreativeOS", role="rights marketplace (assets + IP)",
                   port=PORT)


init_db()  # ensure tables exist (also under gunicorn)

if __name__ == "__main__":
    # Port registered in /PORTS.md; override with RIGHTSFORGE_PORT if you need a scratch instance.
    # HOST defaults to loopback-only; set HOST=0.0.0.0 (see scripts/run_for_phone.py) to reach
    # this from another device on the same network, e.g. a phone.
    app.run(debug=True, host=os.environ.get("HOST", "127.0.0.1"), port=PORT)
