"""
CreatorStack — the competitions layer of CreativeOS.

Brands post creative challenges; creators submit concepts; the sponsor picks a winner and the
concept becomes a funded production. Talent discovered through what you make, not a résumé.

Schema follows docs/database-schema.md's CreatorStack section exactly:
  challenges  id, sponsor, title, brief, prize_cents, submit_deadline, status(open|judging|awarded)
  submissions id, challenge_id, creator, pitch
  awards      id, challenge_id, submission_id, funding_cents
On award: emit `challenge.won` -> Reputation, FrameVault, Payments (docs/database-schema.md:182).

Two seams to FrameVault, same pattern as FilmCrew and RightsForge:
  1. IDENTITY — /api/authenticate: one login across CreativeOS.
  2. CREDIT   — /api/credit: an award writes `challenge.won` onto the winner's FrameVault.

Community voting is real (one vote per FrameVault identity per submission, enforced by a unique
constraint) — it's the signal the sponsor sees when picking a winner, not a cosmetic counter.

Isolation (per companies/creativeos/framevault/ARCHITECTURE.md):
  * Own folder, own database (creatorstack.db), own port (5005, see /PORTS.md).
  * CreatorStack NEVER touches FrameVault's, FilmCrew's, or RightsForge's database.

Run:  python app.py   ->  http://127.0.0.1:5005   (FrameVault should be running on 5001)
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
DB_PATH = os.environ.get("CS_DB", os.path.join(APP_DIR, "creatorstack.db"))
# Local disk today; swap save_upload() for a Supabase storage client later
# without touching any route. Gated to the submitter + the challenge's own
# sponsor only — this is a competition, not a marketplace: nothing here
# should let other entrants see a rival's script before judging.
UPLOAD_DIR = os.path.join(APP_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50MB — a script/pitch deck, not raw footage

# Port comes from the environment so you never edit code to move it.
# Registered in /PORTS.md — CreativeOS owns the 5000–5099 block; CreatorStack is 5005.
PORT = int(os.environ.get("CREATORSTACK_PORT", 5005))

FRAMEVAULT_URL = os.environ.get("FRAMEVAULT_URL", "http://127.0.0.1:5001")
SERVICE_KEY = os.environ.get("FV_SERVICE_KEY", "creativeos-dev-service-key")

app = Flask(__name__)
app.secret_key = os.environ.get("CS_SECRET", "creatorstack-dev-secret-change-in-production")

CHALLENGE_STATUSES = ["open", "judging", "awarded"]


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- #
#  Database (own store)                                                       #
# --------------------------------------------------------------------------- #
SCHEMA = """
CREATE TABLE IF NOT EXISTS challenges (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  sponsor_handle TEXT NOT NULL,
  sponsor_name   TEXT NOT NULL,
  title          TEXT NOT NULL,
  brief          TEXT DEFAULT '',
  criteria       TEXT DEFAULT '',
  prize          INTEGER DEFAULT 0,
  submit_deadline TEXT DEFAULT '',
  status         TEXT DEFAULT 'open',      -- open | judging | awarded
  created_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS submissions (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  challenge_id   INTEGER NOT NULL REFERENCES challenges(id),
  creator_handle TEXT DEFAULT '',
  creator_name   TEXT NOT NULL,
  on_fv          INTEGER NOT NULL DEFAULT 0,
  pitch          TEXT NOT NULL,
  stored_name    TEXT DEFAULT '',   -- filename on disk under static/uploads/, '' = pitch text only
  filename       TEXT DEFAULT '',
  mime           TEXT DEFAULT '',
  bytes          INTEGER DEFAULT 0,
  content_hash   TEXT DEFAULT '',   -- SHA-256 — tamper-evident proof of exactly what was submitted
  created_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS votes (
  submission_id  INTEGER NOT NULL REFERENCES submissions(id),
  voter_handle   TEXT NOT NULL,
  PRIMARY KEY (submission_id, voter_handle)
);
CREATE TABLE IF NOT EXISTS awards (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  challenge_id   INTEGER NOT NULL REFERENCES challenges(id),
  submission_id  INTEGER NOT NULL REFERENCES submissions(id),
  funding        INTEGER DEFAULT 0,
  credited       INTEGER NOT NULL DEFAULT 0,
  credit_note    TEXT DEFAULT '',
  created_at     TEXT NOT NULL
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
    original submissions table. Add them if missing."""
    cols = {row[1] for row in db.execute("PRAGMA table_info(submissions)")}
    for col, decl in (("stored_name", "TEXT DEFAULT ''"), ("filename", "TEXT DEFAULT ''"),
                       ("mime", "TEXT DEFAULT ''"), ("bytes", "INTEGER DEFAULT 0"),
                       ("content_hash", "TEXT DEFAULT ''")):
        if col not in cols:
            db.execute(f"ALTER TABLE submissions ADD COLUMN {col} {decl}")


def save_upload(file_storage):
    """Save an uploaded file to local disk and hash it. Returns
    (stored_name, filename, mime, bytes, sha256_hex) or all-empty/0 if no
    file was given."""
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


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    _migrate(db)
    if db.execute("SELECT COUNT(*) FROM challenges").fetchone()[0] == 0:
        seed(db)
    db.commit()
    db.close()


def seed(db):
    ts = now_iso()
    cid = db.execute(
        "INSERT INTO challenges (sponsor_handle, sponsor_name, title, brief, criteria, prize, "
        "submit_deadline, status, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        ("ott", "Lumen Films (via OTT)", "“Neon Dusk” — a 60-second brand film",
         "Pitch a concept for a one-minute cinematic spot about a city coming alive at nightfall. "
         "We're judging on mood, originality and a shootable vision — not polish. The winning "
         "concept gets fully funded into production.",
         "Mood 40% · Originality 40% · Feasibility 20%", 5000, "2026-08-01", "open", ts),
    ).lastrowid
    for name, handle, on_fv, pitch, votes in [
        ("Maya Rún", "", 0, "“Signal Fires” — the city's neon comes alive as beacons answering each other across rooftops.", 218),
        ("OTT", "ott", 1, "“Dusk Protocol” — a single continuous take following the city's power grid switching on, block by block.", 190),
        ("Rhea Kapoor", "", 0, "“Sodium” — shot entirely in sodium-vapor amber, a love letter to old streetlight color.", 164),
    ]:
        sid = db.execute(
            "INSERT INTO submissions (challenge_id, creator_handle, creator_name, on_fv, pitch, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (cid, handle, name, on_fv, pitch, ts),
        ).lastrowid
        for i in range(votes):
            db.execute("INSERT OR IGNORE INTO votes (submission_id, voter_handle) VALUES (?,?)",
                      (sid, f"seed-voter-{sid}-{i}"))

    # A second, already-awarded challenge so /?status=awarded and the credit history has proof.
    cid2 = db.execute(
        "INSERT INTO challenges (sponsor_handle, sponsor_name, title, brief, criteria, prize, "
        "submit_deadline, status, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        ("", "Studio Kestrel", "“Cold Open” — a 30-second title sequence concept",
         "A title sequence for an anthology thriller series. Sets the tone for everything after it.",
         "Tone 50% · Craft 50%", 3000, "2026-06-01", "awarded", ts),
    ).lastrowid
    sid2 = db.execute(
        "INSERT INTO submissions (challenge_id, creator_handle, creator_name, on_fv, pitch, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (cid2, "ott", "OTT", 1, "A single unbroken shot through a model city, lights dying one by one.", ts),
    ).lastrowid
    db.execute(
        "INSERT INTO awards (challenge_id, submission_id, funding, credited, credit_note, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (cid2, sid2, 3000, 0, "Seeded historical award (not re-credited).", ts),
    )


# --------------------------------------------------------------------------- #
#  Cross-service calls — the seams to FrameVault                              #
# --------------------------------------------------------------------------- #
def framevault_post(path, payload, timeout=5):
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


def credit_framevault(handle, title, prize, payer_handle=""):
    """THE MAGIC MOMENT: winning a challenge becomes verified history on the winner's FrameVault.

    payer_handle (the sponsor) lets FrameVault write the other half of the same
    transaction — a real ledger entry on the sponsor's side, not just the winner's."""
    return framevault_post("/api/credit", {
        "handle": handle,
        "payer_handle": payer_handle,
        "kind": "challenge.won",
        "source": "CreatorStack",
        "weight": 6,
        "amount": prize,
        "review": {
            "author_name": "CreatorStack sponsor", "rating": 5,
            "body": f"Won “{title}” — concept selected for funding (£{prize:,}).",
            "context": f"Won “{title}” · via CreatorStack",
        },
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
        return redirect(request.args.get("next") or url_for("challenges"))
    if "handle" in session:
        return redirect(url_for("challenges"))
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --------------------------------------------------------------------------- #
#  Pages                                                                       #
# --------------------------------------------------------------------------- #
def challenge_extra(db, c):
    d = dict(c)
    subs = db.execute(
        "SELECT s.*, (SELECT COUNT(*) FROM votes v WHERE v.submission_id=s.id) AS vote_count "
        "FROM submissions s WHERE s.challenge_id=? ORDER BY vote_count DESC, s.id", (c["id"],)
    ).fetchall()
    d["submissions"] = subs
    d["award"] = db.execute(
        "SELECT a.*, s.creator_name, s.creator_handle FROM awards a "
        "JOIN submissions s ON s.id=a.submission_id WHERE a.challenge_id=?", (c["id"],)
    ).fetchone()
    return d


@app.route("/")
def challenges():
    db = get_db()
    status = request.args.get("status", "open")
    if status not in CHALLENGE_STATUSES:
        status = "open"
    rows = db.execute(
        "SELECT * FROM challenges WHERE status=? ORDER BY id DESC", (status,)
    ).fetchall()
    listing = [challenge_extra(db, r) for r in rows]
    stats = {
        "open": db.execute("SELECT COUNT(*) c FROM challenges WHERE status='open'").fetchone()["c"],
        "awarded": db.execute("SELECT COUNT(*) c FROM challenges WHERE status='awarded'").fetchone()["c"],
        "submissions": db.execute("SELECT COUNT(*) c FROM submissions").fetchone()["c"],
        "prize_pool": db.execute(
            "SELECT COALESCE(SUM(prize),0) s FROM challenges WHERE status='open'"
        ).fetchone()["s"],
    }
    return render_template("challenges.html", status=status, listing=listing, stats=stats)


@app.route("/challenge/<int:cid>")
def challenge_page(cid):
    db = get_db()
    row = db.execute("SELECT * FROM challenges WHERE id=?", (cid,)).fetchone()
    if row is None:
        abort(404)
    me = current_user()
    already_submitted = bool(me) and db.execute(
        "SELECT 1 FROM submissions WHERE challenge_id=? AND creator_handle=?", (cid, me["handle"] if me else "")
    ).fetchone()
    return render_template("challenge.html", c=challenge_extra(db, row), already_submitted=already_submitted)


@app.route("/post")
@login_required
def post_page():
    return render_template("post.html")


@app.route("/mine")
@login_required
def mine_page():
    db = get_db()
    me = current_user()
    sponsoring = [challenge_extra(db, r) for r in db.execute(
        "SELECT * FROM challenges WHERE sponsor_handle=? ORDER BY id DESC", (me["handle"],)
    ).fetchall()]
    entering = db.execute(
        "SELECT s.*, c.title, c.status challenge_status, c.id challenge_id FROM submissions s "
        "JOIN challenges c ON c.id=s.challenge_id WHERE s.creator_handle=? ORDER BY s.id DESC",
        (me["handle"],),
    ).fetchall()
    won = db.execute(
        "SELECT a.*, c.title FROM awards a JOIN submissions s ON s.id=a.submission_id "
        "JOIN challenges c ON c.id=a.challenge_id WHERE s.creator_handle=?", (me["handle"],)
    ).fetchall()
    return render_template("mine.html", sponsoring=sponsoring, entering=entering, won=won)


# --------------------------------------------------------------------------- #
#  JSON API                                                                    #
# --------------------------------------------------------------------------- #
@app.post("/api/challenge")
@api_login_required
def api_create_challenge():
    d = request.get_json(force=True)
    title = (d.get("title") or "").strip()
    if not title:
        return jsonify(ok=False, error="A title is required."), 400
    me = current_user()
    db = get_db()
    cid = db.execute(
        "INSERT INTO challenges (sponsor_handle, sponsor_name, title, brief, criteria, prize, "
        "submit_deadline, status, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (me["handle"], me["name"], title, (d.get("brief") or "").strip(),
         (d.get("criteria") or "").strip(), int(d.get("prize") or 0),
         (d.get("submit_deadline") or "").strip(), "open", now_iso()),
    ).lastrowid
    db.commit()
    return jsonify(ok=True, id=cid)


@app.post("/api/challenge/<int:cid>/submit")
@api_login_required
def api_submit(cid):
    me = current_user()
    pitch = (request.form.get("pitch") or "").strip()
    try:
        stored_name, filename, mime, size, content_hash = save_upload(request.files.get("file"))
    except ValueError as e:
        return jsonify(ok=False, error=str(e)), 400
    if not pitch and not filename:
        return jsonify(ok=False, error="A pitch or a file is required."), 400
    db = get_db()
    c = db.execute("SELECT * FROM challenges WHERE id=?", (cid,)).fetchone()
    if c is None:
        return jsonify(ok=False, error="Unknown challenge."), 404
    if c["status"] != "open":
        return jsonify(ok=False, error="This challenge is no longer accepting submissions."), 409
    if db.execute("SELECT 1 FROM submissions WHERE challenge_id=? AND creator_handle=?",
                  (cid, me["handle"])).fetchone():
        return jsonify(ok=False, error="You've already submitted to this challenge."), 409
    sid = db.execute(
        "INSERT INTO submissions (challenge_id, creator_handle, creator_name, on_fv, pitch, "
        "stored_name, filename, mime, bytes, content_hash, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (cid, me["handle"], me["name"], 1, pitch or f"(see attached: {filename})",
         stored_name or "", filename, mime, size, content_hash, now_iso()),
    ).lastrowid
    db.commit()
    return jsonify(ok=True, id=sid)


def can_view_submission_file(handle, challenge_row, submission_row):
    """A competition, not a marketplace: only the person who submitted it and
    the challenge's own sponsor (who has to judge it) can see the attached
    file — never another entrant, and never a visitor who isn't logged in."""
    if not handle or not submission_row["stored_name"]:
        return False
    return handle == submission_row["creator_handle"] or handle == challenge_row["sponsor_handle"]


@app.get("/api/submission/<int:sid>/download")
@login_required
def download_submission_file(sid):
    db = get_db()
    sub = db.execute("SELECT * FROM submissions WHERE id=?", (sid,)).fetchone()
    if sub is None or not sub["stored_name"]:
        abort(404)
    c = db.execute("SELECT * FROM challenges WHERE id=?", (sub["challenge_id"],)).fetchone()
    me = current_user()
    if not can_view_submission_file(me["handle"], c, sub):
        abort(403)
    return send_from_directory(UPLOAD_DIR, sub["stored_name"], as_attachment=True,
                                download_name=sub["filename"] or sub["stored_name"])


@app.post("/api/submission/<int:sid>/vote")
@api_login_required
def api_vote(sid):
    me = current_user()
    db = get_db()
    if db.execute("SELECT 1 FROM submissions WHERE id=?", (sid,)).fetchone() is None:
        return jsonify(ok=False, error="Unknown submission."), 404
    existing = db.execute("SELECT 1 FROM votes WHERE submission_id=? AND voter_handle=?",
                          (sid, me["handle"])).fetchone()
    if existing:
        db.execute("DELETE FROM votes WHERE submission_id=? AND voter_handle=?", (sid, me["handle"]))
        db.commit()
        return jsonify(ok=True, voted=False)
    db.execute("INSERT INTO votes (submission_id, voter_handle) VALUES (?,?)", (sid, me["handle"]))
    db.commit()
    return jsonify(ok=True, voted=True)


@app.post("/api/challenge/<int:cid>/award")
@api_login_required
def api_award(cid):
    """Only the sponsor can award. Fires the FrameVault credit — the magic moment."""
    me = current_user()
    submission_id = request.get_json(force=True).get("submission_id")
    db = get_db()
    c = db.execute("SELECT * FROM challenges WHERE id=?", (cid,)).fetchone()
    if c is None:
        return jsonify(ok=False, error="Unknown challenge."), 404
    if c["sponsor_handle"] != me["handle"]:
        return jsonify(ok=False, error="Only the sponsor can award this challenge."), 403
    if c["status"] == "awarded":
        return jsonify(ok=False, error="This challenge has already been awarded."), 409
    sub = db.execute("SELECT * FROM submissions WHERE id=? AND challenge_id=?",
                     (submission_id, cid)).fetchone()
    if sub is None:
        return jsonify(ok=False, error="Unknown submission."), 404

    ts = now_iso()
    aid = db.execute(
        "INSERT INTO awards (challenge_id, submission_id, funding, created_at) VALUES (?,?,?,?)",
        (cid, submission_id, c["prize"], ts),
    ).lastrowid
    db.execute("UPDATE challenges SET status='awarded' WHERE id=?", (cid,))

    resp = {"ok": True, "credited": False}
    if sub["on_fv"] and sub["creator_handle"]:
        ok, detail = credit_framevault(sub["creator_handle"], c["title"], c["prize"],
                                        payer_handle=c["sponsor_handle"])
        note = "Credit written to FrameVault." if ok else f"FrameVault not updated: {detail.get('error','error')}"
        db.execute("UPDATE awards SET credited=?, credit_note=? WHERE id=?", (1 if ok else 0, note, aid))
        resp.update(credited=ok, note=note, public_url=f"{FRAMEVAULT_URL}/@{sub['creator_handle']}")
    else:
        note = "Awarded. The winner isn't on FrameVault yet, so no credit was written."
        db.execute("UPDATE awards SET credit_note=? WHERE id=?", (note, aid))
        resp.update(note=note)

    db.commit()
    return jsonify(resp)


@app.get("/api/search")
def api_search():
    """Read-only search across challenges, for the command palette. Additive
    endpoint — doesn't touch any existing route."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 1:
        return jsonify(results=[])
    like = f"%{q}%"
    db = get_db()
    results = []
    for c in db.execute(
        "SELECT id, title, sponsor_name, status FROM challenges WHERE title LIKE ? OR sponsor_name LIKE ? "
        "ORDER BY id DESC LIMIT 8",
        (like, like),
    ).fetchall():
        results.append({"type": "Challenge", "title": c["title"],
                         "subtitle": c["sponsor_name"] + " · " + c["status"], "url": f"/challenge/{c['id']}"})
    return jsonify(results=results)


@app.get("/__whoami")
def whoami():
    """Identity probe for scripts/check_ports.py — a port can be identified, not guessed."""
    return jsonify(app="CreatorStack", track="CreativeOS", role="competitions", port=PORT)


init_db()  # ensure tables exist (also under gunicorn)

if __name__ == "__main__":
    # Port registered in /PORTS.md; override with CREATORSTACK_PORT if you need a scratch instance.
    # HOST defaults to loopback-only; set HOST=0.0.0.0 (see scripts/run_for_phone.py) to reach
    # this from another device on the same network, e.g. a phone.
    app.run(debug=True, host=os.environ.get("HOST", "127.0.0.1"), port=PORT)
