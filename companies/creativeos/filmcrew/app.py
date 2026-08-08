"""
FilmCrew — the collaboration / hiring layer of CreativeOS.

Staff a production end to end: create a project, post roles, review ranked applicants, make an
offer, and run the contract through to payment. When a contract is PAID, FilmCrew writes a verified
credit onto that creator's FrameVault — two independent services, each with its own database,
talking over an API. That cross-product loop is the whole thesis: "one platform, not six companies."

Two seams to FrameVault (both real, both over HTTP with a shared service key):
  1. IDENTITY  — /api/authenticate: you log into FilmCrew with your FrameVault account.
                 FilmCrew never stores your password; FrameVault stays the source of truth.
  2. CREDIT    — /api/credit: a completed hire enriches the creator's identity + reputation.
                 In the full build this travels the event bus as `hire.completed`; the contract
                 is identical — this is that seam, made real.

Why the credit fires on PAID (not on "hire"): a credit should mean work actually delivered and
money actually moved. Firing earlier would let anyone mint reputation by clicking "hire".

Isolation (per companies/creativeos/framevault/ARCHITECTURE.md):
  * Own folder, own database (filmcrew.db), own port (5002, see /PORTS.md).
  * FilmCrew NEVER touches FrameVault's database.

Run:  python app.py   ->  http://127.0.0.1:5002   (FrameVault should be running on 5001)
"""

import os
import json
import sqlite3
import datetime
import urllib.request
import urllib.error
from functools import wraps

from flask import (
    Flask, request, jsonify, render_template, redirect, url_for, abort, g, session
)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("FC_DB", os.path.join(APP_DIR, "filmcrew.db"))

# Port comes from the environment so you never edit code to move it.
# Registered in /PORTS.md — CreativeOS owns the 5000–5099 block; FilmCrew is 5002.
PORT = int(os.environ.get("FILMCREW_PORT", 5002))

# Where FrameVault lives, and the shared key it trusts (must match FrameVault's FV_SERVICE_KEY).
FRAMEVAULT_URL = os.environ.get("FRAMEVAULT_URL", "http://127.0.0.1:5001")
SERVICE_KEY = os.environ.get("FV_SERVICE_KEY", "creativeos-dev-service-key")

app = Flask(__name__)
# Session cookie secret. FilmCrew stores only *who you are*, never your password.
app.secret_key = os.environ.get("FC_SECRET", "filmcrew-dev-secret-change-in-production")

PROJECT_STAGES = [
    ("drafting", "Drafting"),
    ("open", "Open roles"),
    ("in_production", "In production"),
    ("wrapped", "Wrapped"),
]
# A contract walks these in order; the FrameVault credit fires on the final step.
CONTRACT_FLOW = ["offered", "accepted", "delivered", "paid"]


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- #
#  Database (own store — never shared with FrameVault)                        #
# --------------------------------------------------------------------------- #
SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  title        TEXT NOT NULL,
  producer     TEXT NOT NULL,
  owner_handle TEXT DEFAULT '',            -- FrameVault @handle that actually controls this
                                            -- production — '' means no real owner (old demo
                                            -- data), so nobody gets management rights over it.
  summary      TEXT DEFAULT '',
  location     TEXT DEFAULT '',
  status       TEXT DEFAULT 'drafting',    -- drafting | open | in_production | wrapped
  created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS roles (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id),
  title      TEXT NOT NULL,
  detail     TEXT DEFAULT '',
  fee        INTEGER DEFAULT 0,
  status     TEXT DEFAULT 'open'           -- open | closed | filled
);
CREATE TABLE IF NOT EXISTS applicants (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  role_id    INTEGER NOT NULL REFERENCES roles(id),
  name       TEXT NOT NULL,
  handle     TEXT DEFAULT '',              -- FrameVault @handle ('' = not on FrameVault yet)
  on_fv      INTEGER NOT NULL DEFAULT 0,
  verified   INTEGER NOT NULL DEFAULT 0,   -- FrameVault-verified — the real credibility signal
  match_pct  INTEGER,                      -- NULL for an organic self-application: there's no
                                            -- real matching model here, so it's honest to show
                                            -- nothing rather than a fabricated percentage
  note       TEXT DEFAULT '',
  status     TEXT DEFAULT 'applied'        -- applied | shortlisted | offered | hired | declined
);
CREATE TABLE IF NOT EXISTS production_collaborators (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id),
  handle     TEXT NOT NULL,
  name       TEXT NOT NULL,
  title      TEXT DEFAULT 'Manager',       -- free-text: Manager, Producer, Coordinator...
  status     TEXT DEFAULT 'pending',       -- pending | active — same accept-step pattern as
                                            -- Studio's workspace invites, not an auto-add
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS contracts (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id   INTEGER NOT NULL REFERENCES projects(id),
  role_id      INTEGER NOT NULL REFERENCES roles(id),
  applicant_id INTEGER NOT NULL REFERENCES applicants(id),
  fee          INTEGER DEFAULT 0,
  status       TEXT DEFAULT 'offered',     -- offered | accepted | delivered | paid
  credited     INTEGER NOT NULL DEFAULT 0, -- did the FrameVault credit succeed?
  credit_note  TEXT DEFAULT '',
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS talent (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  name     TEXT NOT NULL,
  handle   TEXT DEFAULT '',
  on_fv    INTEGER NOT NULL DEFAULT 0,
  craft    TEXT DEFAULT '',
  location TEXT DEFAULT '',
  rate     INTEGER DEFAULT 0,
  bio      TEXT DEFAULT ''
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
    exists from an older version of SCHEMA — this filmcrew.db predates
    'location'/'status'/'created_at' on projects. Add whatever's missing."""
    cols = {row[1] for row in db.execute("PRAGMA table_info(projects)")}
    if "location" not in cols:
        db.execute("ALTER TABLE projects ADD COLUMN location TEXT DEFAULT ''")
    if "status" not in cols:
        db.execute("ALTER TABLE projects ADD COLUMN status TEXT DEFAULT 'drafting'")
    if "created_at" not in cols:
        db.execute("ALTER TABLE projects ADD COLUMN created_at TEXT DEFAULT ''")
    if "owner_handle" not in cols:
        db.execute("ALTER TABLE projects ADD COLUMN owner_handle TEXT DEFAULT ''")
    # A fresh column defaults every existing row to '' (no owner) — fine for
    # most seed productions, but Halcyon and Meridian II were always meant to
    # be OTT's own (see seed()). Runs every start, but the WHERE makes it a
    # no-op once applied — needed because an already-added column skips the
    # block above on later runs, so this can't live inside that "if".
    db.execute("UPDATE projects SET owner_handle='ott' WHERE title IN ('Halcyon', 'Meridian II') "
               "AND owner_handle=''")

    cols = {row[1] for row in db.execute("PRAGMA table_info(applicants)")}
    if "verified" not in cols:
        db.execute("ALTER TABLE applicants ADD COLUMN verified INTEGER NOT NULL DEFAULT 0")
    # Same backfill problem as owner_handle above: a fresh column can't
    # retroactively know which existing applicant rows should be marked
    # verified. OTT is the one seeded FrameVault-verified account.
    db.execute("UPDATE applicants SET verified=1 WHERE handle='ott' AND on_fv=1 AND verified=0")


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    _migrate(db)
    if db.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0:
        seed(db)
    db.commit()
    db.close()


def seed(db):
    ts = now_iso()

    def project(title, producer, summary, location, status, owner_handle=""):
        return db.execute(
            "INSERT INTO projects (title, producer, owner_handle, summary, location, status, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (title, producer, owner_handle, summary, location, status, ts),
        ).lastrowid

    def role(pid, title, detail, fee, status="open"):
        return db.execute(
            "INSERT INTO roles (project_id, title, detail, fee, status) VALUES (?,?,?,?,?)",
            (pid, title, detail, fee, status),
        ).lastrowid

    def applicant(rid, name, handle, on_fv, match, note, status="applied", verified=False):
        return db.execute(
            "INSERT INTO applicants (role_id, name, handle, on_fv, verified, match_pct, note, status) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (rid, name, handle, on_fv, int(verified), match, note, status),
        ).lastrowid

    # 1 — Halcyon: OTT's own production (owner_handle set) — the live one with
    # an open DP role, used to demo the owner-side management flow.
    p1 = project("Halcyon", "Studio Kestrel",
                 "A 6-day feature shoot in London. Night exteriors, practical light, controlled shadow.",
                 "London", "open", owner_handle="ott")
    r1 = role(p1, "Director of Photography",
              "6-day shoot · night exteriors · shadow-led, practical sources", 1200)
    applicant(r1, "OTT", "ott", 1, 96,
              "Deakins-influenced DP. Verified provenance on 4 works. Available now.", verified=True)
    applicant(r1, "Aria Lindqvist", "", 0, 90, "Strong operator, 22 credits. Not on FrameVault yet.")
    applicant(r1, "Tomás Neruda", "", 0, 84, "Great with low light. Available in 3 days.")
    r1b = role(p1, "Colorist", "Grade in DaVinci · warm, filmic, low-contrast highlights", 600)
    applicant(r1b, "Kojo Mensah", "", 0, 88, "Specialises in warm filmic grades.")

    # 2 — Nightshift: someone ELSE's production (no owner_handle) — used to
    # demo what a non-owner ("apply only, no management") view looks like.
    p2 = project("Nightshift", "Maya Rún",
                 "Short film. Two-hander, single location, heavy practical lighting.",
                 "Manchester", "in_production")
    r2 = role(p2, "Sound Recordist", "3-day shoot · dialogue-heavy interiors", 480, "filled")
    applicant(r2, "Sena Okafor", "", 0, 92, "Location sound specialist.", "hired")

    # 3 — Meridian II: OTT's own, drafting, no roles posted yet.
    project("Meridian II", "OTT",
            "Music video concept. One continuous take, neon practicals, rain machine.",
            "London", "drafting", owner_handle="ott")

    # 4 — Cold Open: wrapped, with a historical contract.
    p4 = project("Cold Open", "Theo Marchetti",
                 "Funded CreatorStack concept, delivered and paid.", "Bristol", "wrapped")
    r4 = role(p4, "Director of Photography", "2-day shoot", 900, "filled")
    a4 = applicant(r4, "OTT", "ott", 1, 95, "Won the concept, shot the piece.", "hired", verified=True)
    db.execute(
        "INSERT INTO contracts (project_id, role_id, applicant_id, fee, status, credited, "
        "credit_note, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (p4, r4, a4, 900, "paid", 0, "Seeded historical contract (not re-credited).", ts, ts),
    )

    # Talent directory for discovery
    for name, handle, on_fv, craft, loc, rate, bio in [
        ("OTT", "ott", 1, "Director of Photography", "London", 1200,
         "Shadow-led cinematography. Verified provenance on every piece."),
        ("Aria Lindqvist", "", 0, "Director of Photography", "London", 1150,
         "22 credits. Operator and DP."),
        ("Kojo Mensah", "", 0, "Colorist", "Remote", 620, "Warm filmic grades, DaVinci."),
        ("Sena Okafor", "", 0, "Sound Recordist", "Manchester", 480, "Location sound specialist."),
        ("Tomás Neruda", "", 0, "Director of Photography", "Lisbon", 1000, "Low-light specialist."),
        ("Rhea Kapoor", "", 0, "Editor", "London", 700, "Narrative shorts and docs."),
    ]:
        db.execute(
            "INSERT INTO talent (name, handle, on_fv, craft, location, rate, bio) "
            "VALUES (?,?,?,?,?,?,?)",
            (name, handle, on_fv, craft, loc, rate, bio),
        )


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


def credit_framevault(handle, role_title, project_title, producer, fee=0, payer_handle=""):
    """THE MAGIC MOMENT: a paid contract becomes verified history on the creator's FrameVault.

    payer_handle (the production owner) lets FrameVault write the other half of the
    same transaction — a real ledger entry on the payer's side, not just the earner's."""
    return framevault_post("/api/credit", {
        "handle": handle,
        "payer_handle": payer_handle,
        "kind": "hire.completed",
        "source": "FilmCrew",
        "weight": 5,
        "amount": fee,
        "review": {
            "author_name": producer,
            "rating": 5,
            "body": f"Hired as {role_title} on “{project_title}”. Delivered and paid — a pleasure on set.",
            "context": f"Hired for “{project_title}” · via FilmCrew",
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


def is_owner(db, project_row, handle):
    """A production has one real owner (owner_handle) — old demo productions
    with no real owner ('') are manageable by nobody, not by whoever happens
    to be logged in. A collaborator with an active row also counts: they're
    allowed to help run the production, just not to have invited themselves."""
    if not handle or not project_row["owner_handle"]:
        return False
    if handle == project_row["owner_handle"]:
        return True
    return db.execute(
        "SELECT 1 FROM production_collaborators WHERE project_id=? AND handle=? AND status='active'",
        (project_row["id"], handle),
    ).fetchone() is not None


def _project_of_applicant(db, k):
    a = db.execute("SELECT role_id FROM applicants WHERE id=?", (k["aid"],)).fetchone()
    if a is None:
        return None
    r = db.execute("SELECT project_id FROM roles WHERE id=?", (a["role_id"],)).fetchone()
    return r["project_id"] if r else None


def _project_of_role(db, k):
    r = db.execute("SELECT project_id FROM roles WHERE id=?", (k["rid"],)).fetchone()
    return r["project_id"] if r else None


def _project_of_contract(db, k):
    c = db.execute("SELECT project_id FROM contracts WHERE id=?", (k["cid"],)).fetchone()
    return c["project_id"] if c else None


def owner_required(get_project_id):
    """Decorator factory: get_project_id(kwargs) -> project id, resolved from
    the route's own URL params (a role id, contract id, etc. all trace back
    to one project). 403s anyone who isn't that project's real owner or an
    active collaborator — including someone who's logged in."""
    def decorator(view):
        @wraps(view)
        def wrapped(*a, **k):
            if "handle" not in session:
                return jsonify(ok=False, error="Please log in with your FrameVault account."), 401
            db = get_db()
            me = current_user()
            pid = get_project_id(db, k)
            if pid is None:
                return jsonify(ok=False, error="Not found."), 404
            p = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
            if p is None:
                return jsonify(ok=False, error="Not found."), 404
            if not me or not is_owner(db, p, me["handle"]):
                return jsonify(ok=False, error="Only this production's owner can do that."), 403
            return view(*a, **k)
        return wrapped
    return decorator


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        handle = (request.form.get("handle") or "").strip().lstrip("@").lower()
        password = request.form.get("password") or ""
        ok, data = framevault_post("/api/authenticate", {"handle": handle, "password": password})
        if not ok:
            return render_template("login.html", error=data.get("error", "Login failed.")), 401
        u = data["user"]
        # We store WHO you are — never the password.
        session["handle"] = u["handle"]
        session["name"] = u["display_name"]
        session["verified"] = u["verified"]
        return redirect(request.args.get("next") or url_for("board"))
    if "handle" in session:
        return redirect(url_for("board"))
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --------------------------------------------------------------------------- #
#  Pages                                                                       #
# --------------------------------------------------------------------------- #
@app.route("/")
def board():
    db = get_db()
    projects = db.execute("SELECT * FROM projects ORDER BY id").fetchall()
    cards = {key: [] for key, _ in PROJECT_STAGES}
    for p in projects:
        roles = db.execute("SELECT * FROM roles WHERE project_id=?", (p["id"],)).fetchall()
        open_roles = [r for r in roles if r["status"] == "open"]
        applicants = db.execute(
            "SELECT COUNT(*) c FROM applicants WHERE role_id IN "
            "(SELECT id FROM roles WHERE project_id=?)", (p["id"],)
        ).fetchone()["c"]
        cards.setdefault(p["status"], []).append(
            {"p": p, "roles": len(roles), "open_roles": len(open_roles), "applicants": applicants}
        )
    stats = {
        "projects": len(projects),
        "open_roles": db.execute("SELECT COUNT(*) c FROM roles WHERE status='open'").fetchone()["c"],
        "applicants": db.execute("SELECT COUNT(*) c FROM applicants WHERE status='applied'").fetchone()["c"],
        "in_escrow": db.execute(
            "SELECT COALESCE(SUM(fee),0) s FROM contracts WHERE status IN ('offered','accepted','delivered')"
        ).fetchone()["s"],
    }
    return render_template("board.html", stages=PROJECT_STAGES, cards=cards, stats=stats)


@app.route("/project/<int:pid>")
def project_page(pid):
    db = get_db()
    p = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if p is None:
        abort(404)
    me = current_user()
    owner = bool(me) and is_owner(db, p, me["handle"])
    roles = db.execute("SELECT * FROM roles WHERE project_id=? ORDER BY id", (pid,)).fetchall()
    role_blocks = []
    for r in roles:
        # Verified applicants first (the real credibility signal), then by
        # match — and an organic self-application has no match_pct (NULL),
        # which SQLite already sorts last on DESC, which is what we want:
        # a curated/computed score outranks "just applied," verified or not.
        apps_ = db.execute(
            "SELECT * FROM applicants WHERE role_id=? ORDER BY verified DESC, match_pct DESC",
            (r["id"],),
        ).fetchall()
        contract = db.execute(
            "SELECT * FROM contracts WHERE role_id=? ORDER BY id DESC LIMIT 1", (r["id"],)
        ).fetchone()
        my_application = None
        if me:
            my_application = db.execute(
                "SELECT * FROM applicants WHERE role_id=? AND handle=?", (r["id"], me["handle"])
            ).fetchone()
        role_blocks.append({"role": r, "applicants": apps_, "contract": contract,
                             "my_application": my_application})
    collaborators = db.execute(
        "SELECT * FROM production_collaborators WHERE project_id=? ORDER BY "
        "CASE status WHEN 'active' THEN 0 ELSE 1 END, id", (pid,)
    ).fetchall()
    my_collab_invite = None
    if me and not owner:
        my_collab_invite = db.execute(
            "SELECT * FROM production_collaborators WHERE project_id=? AND handle=? AND status='pending'",
            (pid, me["handle"]),
        ).fetchone()
    return render_template("project.html", p=p, blocks=role_blocks, flow=CONTRACT_FLOW,
                           stages=PROJECT_STAGES, is_owner=owner, collaborators=collaborators,
                           my_collab_invite=my_collab_invite)


@app.route("/talent")
@login_required
def talent_page():
    db = get_db()
    q = (request.args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        rows = db.execute(
            "SELECT * FROM talent WHERE name LIKE ? OR craft LIKE ? OR location LIKE ? "
            "ORDER BY on_fv DESC, name", (like, like, like),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM talent ORDER BY on_fv DESC, name").fetchall()
    me = current_user()
    # Only roles this user actually manages — inviting someone to a role
    # you don't own is the same bug as everything else here.
    open_roles = db.execute(
        "SELECT r.id, r.title, p.title ptitle FROM roles r JOIN projects p ON p.id=r.project_id "
        "WHERE r.status='open' AND (p.owner_handle=? OR EXISTS ("
        "  SELECT 1 FROM production_collaborators c WHERE c.project_id=p.id "
        "  AND c.handle=? AND c.status='active')) ORDER BY r.id",
        (me["handle"], me["handle"]),
    ).fetchall()
    return render_template("talent.html", talent=rows, q=q, open_roles=open_roles)


# --------------------------------------------------------------------------- #
#  JSON API                                                                    #
# --------------------------------------------------------------------------- #
@app.post("/api/project")
@api_login_required
def api_create_project():
    d = request.get_json(force=True)
    title = (d.get("title") or "").strip()
    if not title:
        return jsonify(ok=False, error="A project title is required."), 400
    me = current_user()
    db = get_db()
    pid = db.execute(
        "INSERT INTO projects (title, producer, owner_handle, summary, location, status, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (title, (d.get("producer") or me["name"]).strip(), me["handle"],
         (d.get("summary") or "").strip(), (d.get("location") or "").strip(),
         "drafting", now_iso()),
    ).lastrowid
    db.commit()
    return jsonify(ok=True, id=pid)


@app.post("/api/project/<int:pid>/stage")
@owner_required(lambda db, k: k["pid"])
def api_set_stage(pid):
    stage = (request.get_json(force=True).get("stage") or "").strip()
    if stage not in dict(PROJECT_STAGES):
        return jsonify(ok=False, error="Unknown stage."), 400
    db = get_db()
    db.execute("UPDATE projects SET status=? WHERE id=?", (stage, pid))
    db.commit()
    return jsonify(ok=True, stage=stage)


@app.post("/api/project/<int:pid>/role")
@owner_required(lambda db, k: k["pid"])
def api_post_role(pid):
    d = request.get_json(force=True)
    title = (d.get("title") or "").strip()
    if not title:
        return jsonify(ok=False, error="A role title is required."), 400
    db = get_db()
    rid = db.execute(
        "INSERT INTO roles (project_id, title, detail, fee, status) VALUES (?,?,?,?,'open')",
        (pid, title, (d.get("detail") or "").strip(), int(d.get("fee") or 0)),
    ).lastrowid
    # posting a role moves a drafting project to "open"
    db.execute("UPDATE projects SET status='open' WHERE id=? AND status='drafting'", (pid,))
    db.commit()
    return jsonify(ok=True, id=rid)


@app.post("/api/role/<int:rid>")
@owner_required(_project_of_role)
def api_edit_role(rid):
    """Edit a posted role's title/detail/fee."""
    d = request.get_json(force=True)
    title = (d.get("title") or "").strip()
    if not title:
        return jsonify(ok=False, error="A role title is required."), 400
    db = get_db()
    db.execute("UPDATE roles SET title=?, detail=?, fee=? WHERE id=?",
               (title, (d.get("detail") or "").strip(), int(d.get("fee") or 0), rid))
    db.commit()
    return jsonify(ok=True)


@app.post("/api/role/<int:rid>/delete")
@owner_required(_project_of_role)
def api_delete_role(rid):
    db = get_db()
    if db.execute("SELECT 1 FROM contracts WHERE role_id=?", (rid,)).fetchone():
        return jsonify(ok=False, error="This role already has a contract — close it instead of deleting."), 409
    db.execute("DELETE FROM applicants WHERE role_id=?", (rid,))
    db.execute("DELETE FROM roles WHERE id=?", (rid,))
    db.commit()
    return jsonify(ok=True)


@app.post("/api/role/<int:rid>/status")
@owner_required(_project_of_role)
def api_set_role_status(rid):
    """Manually open or close a role — separate from 'filled', which only
    ever happens automatically when a hire is actually accepted."""
    new = (request.get_json(force=True).get("status") or "").strip()
    if new not in ("open", "closed"):
        return jsonify(ok=False, error="Status must be 'open' or 'closed'."), 400
    db = get_db()
    role = db.execute("SELECT status FROM roles WHERE id=?", (rid,)).fetchone()
    if role["status"] == "filled":
        return jsonify(ok=False, error="This role is already filled."), 409
    db.execute("UPDATE roles SET status=? WHERE id=?", (new, rid))
    db.commit()
    return jsonify(ok=True, status=new)


@app.post("/api/role/<int:rid>/apply")
@api_login_required
def api_apply(rid):
    """A creator applying to an open role themselves — the missing half of
    the picture: everything else here was owner-initiated (invite) or seed
    data. No fabricated match score for an organic application (see the
    match_pct column comment) — ranking falls back to verified status."""
    me = current_user()
    db = get_db()
    r = db.execute("SELECT * FROM roles WHERE id=?", (rid,)).fetchone()
    if r is None:
        return jsonify(ok=False, error="Unknown role."), 404
    if r["status"] != "open":
        return jsonify(ok=False, error="This role isn't open."), 409
    p = db.execute("SELECT * FROM projects WHERE id=?", (r["project_id"],)).fetchone()
    if is_owner(db, p, me["handle"]):
        return jsonify(ok=False, error="You can't apply to your own production's role."), 400
    if db.execute("SELECT 1 FROM applicants WHERE role_id=? AND handle=?",
                  (rid, me["handle"])).fetchone():
        return jsonify(ok=False, error="You've already applied to this role."), 409
    note = (request.get_json(silent=True) or {}).get("note", "").strip()
    db.execute(
        "INSERT INTO applicants (role_id, name, handle, on_fv, verified, match_pct, note, status) "
        "VALUES (?,?,?,1,?,NULL,?,'applied')",
        (rid, me["name"], me["handle"], int(bool(me["verified"])), note),
    )
    db.commit()
    return jsonify(ok=True)


@app.post("/api/applicant/<int:aid>/status")
@owner_required(_project_of_applicant)
def api_applicant_status(aid):
    new = (request.get_json(force=True).get("status") or "").strip()
    if new not in ("applied", "shortlisted", "declined"):
        return jsonify(ok=False, error="Unknown status."), 400
    db = get_db()
    db.execute("UPDATE applicants SET status=? WHERE id=?", (new, aid))
    db.commit()
    return jsonify(ok=True, status=new)


@app.post("/api/applicant/<int:aid>/offer")
@owner_required(_project_of_applicant)
def api_offer(aid):
    """Make an offer — creates the contract at step 1. No credit is written yet."""
    db = get_db()
    a = db.execute("SELECT * FROM applicants WHERE id=?", (aid,)).fetchone()
    if a is None:
        return jsonify(ok=False, error="Unknown applicant."), 404
    r = db.execute("SELECT * FROM roles WHERE id=?", (a["role_id"],)).fetchone()
    if db.execute("SELECT 1 FROM contracts WHERE role_id=?", (r["id"],)).fetchone():
        return jsonify(ok=False, error="This role already has a contract."), 409
    ts = now_iso()
    cid = db.execute(
        "INSERT INTO contracts (project_id, role_id, applicant_id, fee, status, created_at, updated_at) "
        "VALUES (?,?,?,?,'offered',?,?)",
        (r["project_id"], r["id"], aid, r["fee"], ts, ts),
    ).lastrowid
    db.execute("UPDATE applicants SET status='offered' WHERE id=?", (aid,))
    db.commit()
    return jsonify(ok=True, contract_id=cid, status="offered")


@app.post("/api/contract/<int:cid>/advance")
@owner_required(_project_of_contract)
def api_advance(cid):
    """
    Move the contract one step: offered → accepted → delivered → paid.
    Reaching PAID is what fires the FrameVault credit — work delivered, money moved.
    """
    db = get_db()
    c = db.execute("SELECT * FROM contracts WHERE id=?", (cid,)).fetchone()
    if c is None:
        return jsonify(ok=False, error="Unknown contract."), 404
    if c["status"] == "paid":
        return jsonify(ok=False, error="This contract is already complete."), 409

    nxt = CONTRACT_FLOW[CONTRACT_FLOW.index(c["status"]) + 1]
    ts = now_iso()
    db.execute("UPDATE contracts SET status=?, updated_at=? WHERE id=?", (nxt, ts, cid))

    a = db.execute("SELECT * FROM applicants WHERE id=?", (c["applicant_id"],)).fetchone()
    r = db.execute("SELECT * FROM roles WHERE id=?", (c["role_id"],)).fetchone()
    p = db.execute("SELECT * FROM projects WHERE id=?", (c["project_id"],)).fetchone()

    if nxt == "accepted":
        db.execute("UPDATE applicants SET status='hired' WHERE id=?", (a["id"],))
        db.execute("UPDATE roles SET status='filled' WHERE id=?", (r["id"],))
        db.execute("UPDATE projects SET status='in_production' WHERE id=? AND status='open'",
                   (p["id"],))

    resp = {"ok": True, "status": nxt, "credited": False}

    if nxt == "paid":
        # every role on the project filled? then the project is wrapped
        remaining = db.execute(
            "SELECT COUNT(*) c FROM roles WHERE project_id=? AND status='open'", (p["id"],)
        ).fetchone()["c"]
        if remaining == 0:
            db.execute("UPDATE projects SET status='wrapped' WHERE id=?", (p["id"],))

        if a["on_fv"] and a["handle"]:
            ok, detail = credit_framevault(a["handle"], r["title"], p["title"], p["producer"],
                                            fee=r["fee"], payer_handle=p["owner_handle"] or "")
            note = ("Credit written to FrameVault." if ok
                    else f"FrameVault not updated: {detail.get('error', 'error')}")
            db.execute("UPDATE contracts SET credited=?, credit_note=? WHERE id=?",
                       (1 if ok else 0, note, cid))
            resp.update(credited=ok, handle=a["handle"], note=note,
                        public_url=f"{FRAMEVAULT_URL}/@{a['handle']}")
        else:
            note = "Paid. They'll be invited to FrameVault to claim this credit."
            db.execute("UPDATE contracts SET credit_note=? WHERE id=?", (note, cid))
            resp.update(note=note)

    db.commit()
    return jsonify(resp)


@app.post("/api/project/<int:pid>/collaborator")
@owner_required(lambda db, k: k["pid"])
def api_invite_collaborator(pid):
    """Production-level collaborators — managers/producers/coordinators, not
    job roles. Same accept-step pattern as Studio's workspace invites: this
    creates a pending row, not membership."""
    d = request.get_json(force=True)
    handle = (d.get("handle") or "").strip().lstrip("@").lower()
    title = (d.get("title") or "Manager").strip()
    if not handle:
        return jsonify(ok=False, error="A handle is required."), 400
    db = get_db()
    p = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if handle == p["owner_handle"]:
        return jsonify(ok=False, error="They already own this production."), 409
    existing = db.execute(
        "SELECT status FROM production_collaborators WHERE project_id=? AND handle=?", (pid, handle)
    ).fetchone()
    if existing:
        word = "already a collaborator" if existing["status"] == "active" else "already invited, pending"
        return jsonify(ok=False, error=f"@{handle} is {word}."), 409
    name = (d.get("name") or handle).strip()
    db.execute(
        "INSERT INTO production_collaborators (project_id, handle, name, title, status, created_at) "
        "VALUES (?,?,?,?,'pending',?)",
        (pid, handle, name, title, now_iso()),
    )
    db.commit()
    return jsonify(ok=True)


@app.post("/api/project/<int:pid>/collaborator/respond")
@api_login_required
def api_respond_collaborator(pid):
    accept = bool(request.get_json(force=True).get("accept"))
    db = get_db()
    me = current_user()
    row = db.execute(
        "SELECT * FROM production_collaborators WHERE project_id=? AND handle=? AND status='pending'",
        (pid, me["handle"]),
    ).fetchone()
    if row is None:
        return jsonify(ok=False, error="No pending invite for you on that production."), 404
    if accept:
        db.execute("UPDATE production_collaborators SET status='active' WHERE project_id=? AND handle=?",
                   (pid, me["handle"]))
    else:
        db.execute("DELETE FROM production_collaborators WHERE project_id=? AND handle=?",
                   (pid, me["handle"]))
    db.commit()
    return jsonify(ok=True, accepted=accept)


@app.post("/api/talent/<int:tid>/invite")
@api_login_required
def api_invite(tid):
    """The production owner inviting someone onto a role directly — this IS
    the invite feature, not a separate one: it puts them straight onto the
    role as a candidate, same as an inbound application, just owner-initiated."""
    role_id = request.get_json(force=True).get("role_id")
    db = get_db()
    t = db.execute("SELECT * FROM talent WHERE id=?", (tid,)).fetchone()
    r = db.execute("SELECT * FROM roles WHERE id=?", (role_id,)).fetchone()
    if t is None or r is None:
        return jsonify(ok=False, error="Unknown talent or role."), 404
    p = db.execute("SELECT * FROM projects WHERE id=?", (r["project_id"],)).fetchone()
    me = current_user()
    if not is_owner(db, p, me["handle"]):
        return jsonify(ok=False, error="Only this production's owner can invite people."), 403
    if db.execute("SELECT 1 FROM applicants WHERE role_id=? AND name=?",
                  (r["id"], t["name"])).fetchone():
        return jsonify(ok=False, error=f"{t['name']} is already on that role."), 409
    db.execute(
        "INSERT INTO applicants (role_id, name, handle, on_fv, verified, match_pct, note, status) "
        "VALUES (?,?,?,?,0,?,?,'applied')",
        (r["id"], t["name"], t["handle"], t["on_fv"], 80,
         f"Invited from the talent directory. {t['bio']}"),
    )
    db.commit()
    return jsonify(ok=True, message=f"Invited {t['name']} to {r['title']}.")


@app.get("/api/board/stats")
def api_board_stats():
    """Read-only snapshot of the board's header stats, for client-side polling
    so the board feels alive without a page refresh. Same query as board()."""
    db = get_db()
    stats = {
        "projects": db.execute("SELECT COUNT(*) c FROM projects").fetchone()["c"],
        "open_roles": db.execute("SELECT COUNT(*) c FROM roles WHERE status='open'").fetchone()["c"],
        "applicants": db.execute("SELECT COUNT(*) c FROM applicants WHERE status='applied'").fetchone()["c"],
        "in_escrow": db.execute(
            "SELECT COALESCE(SUM(fee),0) s FROM contracts WHERE status IN ('offered','accepted','delivered')"
        ).fetchone()["s"],
    }
    return jsonify(stats)


@app.get("/api/search")
def api_search():
    """Read-only search across productions and talent, for the command palette."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 1:
        return jsonify(results=[])
    like = f"%{q}%"
    db = get_db()
    results = []
    for p in db.execute(
        "SELECT id, title, producer FROM projects WHERE title LIKE ? OR producer LIKE ? ORDER BY id DESC LIMIT 6",
        (like, like),
    ).fetchall():
        results.append({"type": "Production", "title": p["title"], "subtitle": p["producer"], "url": f"/project/{p['id']}"})
    # Talent search is login-gated the same as /talent itself — no browsing
    # who's available while logged out, from the command palette either.
    if current_user():
        for t in db.execute(
            "SELECT id, name, craft FROM talent WHERE name LIKE ? OR craft LIKE ? ORDER BY on_fv DESC, name LIMIT 6",
            (like, like),
        ).fetchall():
            results.append({"type": "Talent", "title": t["name"], "subtitle": t["craft"] or "", "url": f"/talent?q={t['name']}"})
    return jsonify(results=results)


@app.get("/__whoami")
def whoami():
    """Identity probe for scripts/check_ports.py — a port can be identified, not guessed."""
    return jsonify(app="FilmCrew", track="CreativeOS", role="collaboration + hiring", port=PORT)


init_db()  # ensure tables exist (also under gunicorn)

if __name__ == "__main__":
    # Port registered in /PORTS.md; override with FILMCREW_PORT if you need a scratch instance.
    # HOST defaults to loopback-only; set HOST=0.0.0.0 (see scripts/run_for_phone.py) to reach
    # this from another device on the same network, e.g. a phone.
    app.run(debug=True, host=os.environ.get("HOST", "127.0.0.1"), port=PORT)
