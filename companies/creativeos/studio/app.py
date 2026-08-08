"""
OTT Studio — the creator workspace of CreativeOS.

A cloud production workspace: organize projects inside a workspace, track a lightweight asset
tray, orchestrate AI jobs, and publish. Publishing is the magic moment — it announces the work
to the rest of the ecosystem and credits the creator's FrameVault.

Schema follows docs/database-schema.md's OTT Studio section exactly:
  workspaces         id, owner, name
  workspace_members   workspace_id, handle, role(owner|editor|viewer)
  studio_projects     id, workspace_id, name, status, created_at
  studio_assets       id, project_id, label, kind
  ai_jobs             id, project_id, kind, status(queued|running|done|failed)
On publish: emit `project.published` -> Search, FrameVault (docs/database-schema.md:196).

Honesty note on ai_jobs: there is no AI backend here. A job is a real row with a real state
machine (queued -> running -> done), advanced by hand — the same honest pattern FilmCrew uses for
contracts and RightsForge for deals. It demonstrates the ORCHESTRATION workflow without pretending
a network call to a nonexistent AI service happened.

Two seams to FrameVault, same pattern as the other products:
  1. IDENTITY — /api/authenticate: one login across CreativeOS.
  2. CREDIT   — /api/credit: publishing writes `project.published` onto the creator's FrameVault.

Isolation (per companies/creativeos/framevault/ARCHITECTURE.md):
  * Own folder, own database (studio.db), own port (5006, see /PORTS.md).
  * OTT Studio NEVER touches another product's database.

Run:  python app.py   ->  http://127.0.0.1:5006   (FrameVault should be running on 5001)
"""

import os
import json
import sqlite3
import datetime
import urllib.request
import urllib.error
import uuid
from functools import wraps

from flask import (
    Flask, request, jsonify, render_template, redirect, url_for, abort, g, session
)
from werkzeug.utils import secure_filename

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("ST_DB", os.path.join(APP_DIR, "studio.db"))
# Local disk today (mode="local"); swap to Supabase storage later behind the
# same save_upload()/asset_url() pair below without touching any route.
UPLOAD_DIR = os.path.join(APP_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100MB — a real production asset, not a placeholder

# Port comes from the environment so you never edit code to move it.
# Registered in /PORTS.md — CreativeOS owns the 5000–5099 block; OTT Studio is 5006.
PORT = int(os.environ.get("STUDIO_PORT", 5006))

FRAMEVAULT_URL = os.environ.get("FRAMEVAULT_URL", "http://127.0.0.1:5001")
SERVICE_KEY = os.environ.get("FV_SERVICE_KEY", "creativeos-dev-service-key")

app = Flask(__name__)
app.secret_key = os.environ.get("ST_SECRET", "studio-dev-secret-change-in-production")

JOB_PRESETS = ["Proxy transcode", "Auto-sync audio", "Rough color match", "Auto-transcription",
               "Reframe for vertical"]
JOB_FLOW = ["queued", "running", "done"]
ASSET_KINDS = ["video", "image", "audio", "document"]


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- #
#  Database (own store)                                                       #
# --------------------------------------------------------------------------- #
SCHEMA = """
CREATE TABLE IF NOT EXISTS workspaces (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_handle TEXT NOT NULL,
  owner_name  TEXT NOT NULL,
  name        TEXT NOT NULL,
  created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workspace_members (
  workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
  handle       TEXT NOT NULL,
  name         TEXT NOT NULL,
  role         TEXT NOT NULL DEFAULT 'editor',   -- owner | editor | viewer
  PRIMARY KEY (workspace_id, handle)
);
CREATE TABLE IF NOT EXISTS studio_projects (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
  name         TEXT NOT NULL,
  status       TEXT DEFAULT 'active',     -- active | published
  provenance_id TEXT DEFAULT '',
  created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS studio_assets (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id  INTEGER NOT NULL REFERENCES studio_projects(id),
  label       TEXT NOT NULL,
  kind        TEXT DEFAULT 'video',
  stored_name TEXT DEFAULT '',   -- filename on disk under static/uploads/, '' = no file (metadata-only, old rows)
  filename    TEXT DEFAULT '',   -- original filename, for display/download
  mime        TEXT DEFAULT '',
  bytes       INTEGER DEFAULT 0,
  created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_jobs (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES studio_projects(id),
  kind       TEXT NOT NULL,
  status     TEXT DEFAULT 'queued',       -- queued | running | done | failed
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
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
    exists from an older version of SCHEMA — status postdates the original
    workspace_members table. Add it if missing; existing rows default to
    'active' since they already had access under the old auto-add behavior."""
    cols = {row[1] for row in db.execute("PRAGMA table_info(workspace_members)")}
    if "status" not in cols:
        db.execute("ALTER TABLE workspace_members ADD COLUMN status TEXT DEFAULT 'active'")

    cols = {row[1] for row in db.execute("PRAGMA table_info(studio_assets)")}
    for col, decl in (("stored_name", "TEXT DEFAULT ''"), ("filename", "TEXT DEFAULT ''"),
                       ("mime", "TEXT DEFAULT ''"), ("bytes", "INTEGER DEFAULT 0")):
        if col not in cols:
            db.execute(f"ALTER TABLE studio_assets ADD COLUMN {col} {decl}")


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    _migrate(db)
    if db.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0] == 0:
        seed(db)
    db.commit()
    db.close()


def seed(db):
    ts = now_iso()
    wid = db.execute(
        "INSERT INTO workspaces (owner_handle, owner_name, name, created_at) VALUES (?,?,?,?)",
        ("ott", "OTT", "OTT's Workspace", ts),
    ).lastrowid
    db.execute("INSERT INTO workspace_members (workspace_id, handle, name, role) VALUES (?,?,?,?)",
              (wid, "ott", "OTT", "owner"))
    for handle, name, role in [("kojo", "Kojo Mensah", "editor"), ("sena", "Sena Okafor", "viewer")]:
        db.execute("INSERT INTO workspace_members (workspace_id, handle, name, role) VALUES (?,?,?,?)",
                  (wid, handle, name, role))

    pid = db.execute(
        "INSERT INTO studio_projects (workspace_id, name, status, created_at) VALUES (?,?,?,?)",
        (wid, "“Halcyon” — cut", "active", ts),
    ).lastrowid
    for label, kind in [("SC4_night_take3", "video"), ("moodboard_v2", "image"), ("temp_score", "audio")]:
        db.execute("INSERT INTO studio_assets (project_id, label, kind, created_at) VALUES (?,?,?,?)",
                  (pid, label, kind, ts))
    db.execute(
        "INSERT INTO ai_jobs (project_id, kind, status, created_at, updated_at) VALUES (?,?,?,?,?)",
        (pid, "Proxy transcode", "done", ts, ts),
    )
    db.execute(
        "INSERT INTO ai_jobs (project_id, kind, status, created_at, updated_at) VALUES (?,?,?,?,?)",
        (pid, "Auto-sync audio", "running", ts, ts),
    )

    # A second, already-published project, so /discover has real proof.
    pid2 = db.execute(
        "INSERT INTO studio_projects (workspace_id, name, status, created_at) VALUES (?,?,?,?)",
        (wid, "Deakins lighting study", "published", ts),
    ).lastrowid
    db.execute("INSERT INTO studio_assets (project_id, label, kind, created_at) VALUES (?,?,?,?)",
              (pid2, "lighting_diagram_final", "image", ts))


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


def credit_framevault(handle, project_name):
    """THE MAGIC MOMENT: publishing becomes verified portfolio history on the creator's FrameVault."""
    return framevault_post("/api/credit", {
        "handle": handle,
        "kind": "project.published",
        "source": "OTT Studio",
        "weight": 2,
        "review": {
            "author_name": "OTT Studio", "rating": 5,
            "body": f"Published “{project_name}” from the workspace.",
            "context": f"Published “{project_name}” · via OTT Studio",
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
        return redirect(request.args.get("next") or url_for("home"))
    if "handle" in session:
        return redirect(url_for("home"))
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --------------------------------------------------------------------------- #
#  Access helper — workspace membership (owner/editor/viewer)                 #
# --------------------------------------------------------------------------- #
def membership(db, workspace_id, handle):
    """Active membership only — a pending invite grants no access until accepted."""
    return db.execute(
        "SELECT role FROM workspace_members WHERE workspace_id=? AND handle=? AND status='active'",
        (workspace_id, handle),
    ).fetchone()


def can_edit(role_row):
    """Owner/editor can create and mutate content; viewer is read-only."""
    return role_row is not None and role_row["role"] in ("owner", "editor")


# --------------------------------------------------------------------------- #
#  Pages                                                                       #
# --------------------------------------------------------------------------- #
@app.route("/")
def home():
    db = get_db()
    me = current_user()
    my_workspaces = []
    pending_invites = []
    if me:
        my_workspaces = db.execute(
            "SELECT w.* FROM workspaces w JOIN workspace_members m ON m.workspace_id=w.id "
            "WHERE m.handle=? AND m.status='active' ORDER BY w.id", (me["handle"],)
        ).fetchall()
        pending_invites = db.execute(
            "SELECT w.id, w.name, w.owner_name FROM workspaces w JOIN workspace_members m ON m.workspace_id=w.id "
            "WHERE m.handle=? AND m.status='pending' ORDER BY w.id", (me["handle"],)
        ).fetchall()
    published_rows = db.execute(
        "SELECT p.*, w.name workspace_name, w.owner_handle, w.owner_name FROM studio_projects p "
        "JOIN workspaces w ON w.id=p.workspace_id WHERE p.status='published' ORDER BY p.id DESC"
    ).fetchall()
    # "Discover published work" is a feed, not a directory — show the actual
    # asset (a real thumbnail/clip), not just a card that links away to a
    # profile. Prefer a video or image asset that actually has a file;
    # a project with no uploaded assets falls back to a plain card.
    published = []
    for p in published_rows:
        p = dict(p)
        p["cover"] = db.execute(
            "SELECT * FROM studio_assets WHERE project_id=? AND stored_name != '' "
            "ORDER BY CASE kind WHEN 'video' THEN 0 WHEN 'image' THEN 1 ELSE 2 END, id DESC LIMIT 1",
            (p["id"],),
        ).fetchone()
        published.append(p)
    return render_template("home.html", my_workspaces=my_workspaces, published=published,
                            pending_invites=pending_invites)


@app.route("/workspace/<int:wid>")
@login_required
def workspace_page(wid):
    db = get_db()
    me = current_user()
    ws = db.execute("SELECT * FROM workspaces WHERE id=?", (wid,)).fetchone()
    if ws is None:
        abort(404)
    if membership(db, wid, me["handle"]) is None:
        abort(403)
    projects = db.execute(
        "SELECT * FROM studio_projects WHERE workspace_id=? ORDER BY id DESC", (wid,)
    ).fetchall()
    members = db.execute(
        "SELECT * FROM workspace_members WHERE workspace_id=? ORDER BY "
        "CASE role WHEN 'owner' THEN 0 WHEN 'editor' THEN 1 ELSE 2 END, handle", (wid,)
    ).fetchall()
    return render_template("workspace.html", ws=ws, projects=projects, members=members)


@app.route("/project/<int:pid>")
@login_required
def project_page(pid):
    db = get_db()
    me = current_user()
    p = db.execute("SELECT * FROM studio_projects WHERE id=?", (pid,)).fetchone()
    if p is None:
        abort(404)
    if membership(db, p["workspace_id"], me["handle"]) is None:
        abort(403)
    ws = db.execute("SELECT * FROM workspaces WHERE id=?", (p["workspace_id"],)).fetchone()
    assets = db.execute("SELECT * FROM studio_assets WHERE project_id=? ORDER BY id DESC", (pid,)).fetchall()
    jobs = db.execute("SELECT * FROM ai_jobs WHERE project_id=? ORDER BY id DESC", (pid,)).fetchall()
    return render_template("project.html", p=p, ws=ws, assets=assets, jobs=jobs,
                           presets=JOB_PRESETS, asset_kinds=ASSET_KINDS)


# --------------------------------------------------------------------------- #
#  JSON API                                                                    #
# --------------------------------------------------------------------------- #
@app.post("/api/workspace")
@api_login_required
def api_create_workspace():
    d = request.get_json(force=True)
    name = (d.get("name") or "").strip()
    if not name:
        return jsonify(ok=False, error="A workspace name is required."), 400
    me = current_user()
    db = get_db()
    wid = db.execute(
        "INSERT INTO workspaces (owner_handle, owner_name, name, created_at) VALUES (?,?,?,?)",
        (me["handle"], me["name"], name, now_iso()),
    ).lastrowid
    db.execute("INSERT INTO workspace_members (workspace_id, handle, name, role) VALUES (?,?,?,'owner')",
              (wid, me["handle"], me["name"]))
    db.commit()
    return jsonify(ok=True, id=wid)


@app.post("/api/workspace/<int:wid>/invite")
@api_login_required
def api_invite_member(wid):
    d = request.get_json(force=True)
    handle = (d.get("handle") or "").strip().lstrip("@").lower()
    name = (d.get("name") or handle).strip()
    role = (d.get("role") or "editor").strip()
    if role not in ("editor", "viewer"):
        role = "editor"
    if not handle:
        return jsonify(ok=False, error="A handle is required."), 400
    db = get_db()
    me = current_user()
    my_role = membership(db, wid, me["handle"])
    if my_role is None or my_role["role"] != "owner":
        return jsonify(ok=False, error="Only the workspace owner can invite members."), 403
    existing = db.execute(
        "SELECT status FROM workspace_members WHERE workspace_id=? AND handle=?", (wid, handle)
    ).fetchone()
    if existing:
        word = "already a member" if existing["status"] == "active" else "already invited, pending"
        return jsonify(ok=False, error=f"@{handle} is {word}."), 409
    # Pending, not active: an invite is not membership until the invitee
    # accepts it — see api_respond_invite. This was the bug: it used to
    # INSERT straight in as an active member with no consent step at all.
    db.execute("INSERT INTO workspace_members (workspace_id, handle, name, role, status) VALUES (?,?,?,?,'pending')",
              (wid, handle, name, role))
    db.commit()
    return jsonify(ok=True, status="pending")


@app.post("/api/workspace/<int:wid>/invite/respond")
@api_login_required
def api_respond_invite(wid):
    accept = bool(request.get_json(force=True).get("accept"))
    db = get_db()
    me = current_user()
    row = db.execute(
        "SELECT * FROM workspace_members WHERE workspace_id=? AND handle=? AND status='pending'",
        (wid, me["handle"]),
    ).fetchone()
    if row is None:
        return jsonify(ok=False, error="No pending invite for you on that workspace."), 404
    if accept:
        db.execute("UPDATE workspace_members SET status='active' WHERE workspace_id=? AND handle=?",
                   (wid, me["handle"]))
    else:
        db.execute("DELETE FROM workspace_members WHERE workspace_id=? AND handle=?", (wid, me["handle"]))
    db.commit()
    return jsonify(ok=True, accepted=accept)


@app.post("/api/project")
@api_login_required
def api_create_project():
    d = request.get_json(force=True)
    wid = d.get("workspace_id")
    name = (d.get("name") or "").strip()
    if not name:
        return jsonify(ok=False, error="A project name is required."), 400
    db = get_db()
    me = current_user()
    if not can_edit(membership(db, wid, me["handle"])):
        return jsonify(ok=False, error="Viewers can't create projects — ask the workspace owner for editor access."), 403
    pid = db.execute(
        "INSERT INTO studio_projects (workspace_id, name, status, created_at) VALUES (?,?,?,?)",
        (wid, name, "active", now_iso()),
    ).lastrowid
    db.commit()
    return jsonify(ok=True, id=pid)


def save_upload(file_storage):
    """Save an uploaded werkzeug FileStorage to local disk. Returns
    (stored_name, filename, mime, bytes) or (None, "", "", 0) if empty.

    Local disk today — swap this one function for a Supabase storage client
    later and every caller (asset upload, asset replace) keeps working
    unchanged."""
    if not file_storage or not file_storage.filename:
        return None, "", "", 0
    safe = secure_filename(file_storage.filename) or "upload"
    stored_name = f"{uuid.uuid4().hex}_{safe}"
    dest = os.path.join(UPLOAD_DIR, stored_name)
    file_storage.save(dest)
    size = os.path.getsize(dest)
    if size > MAX_UPLOAD_BYTES:
        os.remove(dest)
        raise ValueError(f"File too large ({size // (1024*1024)}MB) — max {MAX_UPLOAD_BYTES // (1024*1024)}MB.")
    return stored_name, file_storage.filename, (file_storage.mimetype or ""), size


def guess_kind(mime):
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("audio/"):
        return "audio"
    return "document"


@app.post("/api/project/<int:pid>/asset")
@api_login_required
def api_add_asset(pid):
    label = (request.form.get("label") or "").strip()
    kind = (request.form.get("kind") or "").strip()
    db = get_db()
    p = db.execute("SELECT * FROM studio_projects WHERE id=?", (pid,)).fetchone()
    if p is None:
        return jsonify(ok=False, error="Unknown project."), 404
    me = current_user()
    if not can_edit(membership(db, p["workspace_id"], me["handle"])):
        return jsonify(ok=False, error="Viewers can't add assets — ask the workspace owner for editor access."), 403

    try:
        stored_name, filename, mime, size = save_upload(request.files.get("file"))
    except ValueError as e:
        return jsonify(ok=False, error=str(e)), 400
    if not label:
        if not filename:
            return jsonify(ok=False, error="A label or a file is required."), 400
        label = filename  # a real upload with no typed label just uses the filename
    if kind not in ASSET_KINDS:
        kind = guess_kind(mime) if mime else "video"

    aid = db.execute(
        "INSERT INTO studio_assets (project_id, label, kind, stored_name, filename, mime, bytes, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (pid, label, kind, stored_name or "", filename, mime, size, now_iso()),
    ).lastrowid
    db.commit()
    return jsonify(ok=True, id=aid)


@app.post("/api/asset/<int:aid>")
@api_login_required
def api_edit_asset(aid):
    """Edit an asset's label/kind, and optionally replace its file."""
    db = get_db()
    a = db.execute("SELECT * FROM studio_assets WHERE id=?", (aid,)).fetchone()
    if a is None:
        return jsonify(ok=False, error="Unknown asset."), 404
    p = db.execute("SELECT * FROM studio_projects WHERE id=?", (a["project_id"],)).fetchone()
    me = current_user()
    if not can_edit(membership(db, p["workspace_id"], me["handle"])):
        return jsonify(ok=False, error="Viewers can't edit assets — ask the workspace owner for editor access."), 403

    label = (request.form.get("label") or a["label"]).strip() or a["label"]
    kind = (request.form.get("kind") or a["kind"]).strip()
    if kind not in ASSET_KINDS:
        kind = a["kind"]

    try:
        stored_name, filename, mime, size = save_upload(request.files.get("file"))
    except ValueError as e:
        return jsonify(ok=False, error=str(e)), 400

    if stored_name:
        old = a["stored_name"]
        db.execute(
            "UPDATE studio_assets SET label=?, kind=?, stored_name=?, filename=?, mime=?, bytes=? WHERE id=?",
            (label, kind, stored_name, filename, mime, size, aid),
        )
        if old:
            old_path = os.path.join(UPLOAD_DIR, old)
            if os.path.exists(old_path):
                os.remove(old_path)
    else:
        db.execute("UPDATE studio_assets SET label=?, kind=? WHERE id=?", (label, kind, aid))
    db.commit()
    return jsonify(ok=True)


@app.post("/api/asset/<int:aid>/delete")
@api_login_required
def api_delete_asset(aid):
    db = get_db()
    a = db.execute("SELECT * FROM studio_assets WHERE id=?", (aid,)).fetchone()
    if a is None:
        return jsonify(ok=False, error="Unknown asset."), 404
    p = db.execute("SELECT * FROM studio_projects WHERE id=?", (a["project_id"],)).fetchone()
    me = current_user()
    if not can_edit(membership(db, p["workspace_id"], me["handle"])):
        return jsonify(ok=False, error="Viewers can't delete assets — ask the workspace owner for editor access."), 403

    db.execute("DELETE FROM studio_assets WHERE id=?", (aid,))
    db.commit()
    if a["stored_name"]:
        path = os.path.join(UPLOAD_DIR, a["stored_name"])
        if os.path.exists(path):
            os.remove(path)
    return jsonify(ok=True)


@app.post("/api/project/<int:pid>/job")
@api_login_required
def api_queue_job(pid):
    d = request.get_json(force=True)
    kind = (d.get("kind") or "").strip()
    if kind not in JOB_PRESETS:
        return jsonify(ok=False, error="Unknown job type."), 400
    db = get_db()
    p = db.execute("SELECT * FROM studio_projects WHERE id=?", (pid,)).fetchone()
    if p is None:
        return jsonify(ok=False, error="Unknown project."), 404
    me = current_user()
    if not can_edit(membership(db, p["workspace_id"], me["handle"])):
        return jsonify(ok=False, error="Viewers can't queue jobs — ask the workspace owner for editor access."), 403
    ts = now_iso()
    jid = db.execute(
        "INSERT INTO ai_jobs (project_id, kind, status, created_at, updated_at) VALUES (?,?,?,?,?)",
        (pid, kind, "queued", ts, ts),
    ).lastrowid
    db.commit()
    return jsonify(ok=True, id=jid)


@app.post("/api/job/<int:jid>/advance")
@api_login_required
def api_advance_job(jid):
    """Move a job one step: queued -> running -> done. No AI runs here (see module docstring) —
    this is a real, honestly-labelled workflow state machine, not a simulated network call."""
    db = get_db()
    job = db.execute("SELECT * FROM ai_jobs WHERE id=?", (jid,)).fetchone()
    if job is None:
        return jsonify(ok=False, error="Unknown job."), 404
    p = db.execute("SELECT * FROM studio_projects WHERE id=?", (job["project_id"],)).fetchone()
    me = current_user()
    if not can_edit(membership(db, p["workspace_id"], me["handle"])):
        return jsonify(ok=False, error="Viewers can't advance jobs — ask the workspace owner for editor access."), 403
    if job["status"] == "done":
        return jsonify(ok=False, error="This job is already done."), 409
    nxt = JOB_FLOW[JOB_FLOW.index(job["status"]) + 1]
    db.execute("UPDATE ai_jobs SET status=?, updated_at=? WHERE id=?", (nxt, now_iso(), jid))
    db.commit()
    return jsonify(ok=True, status=nxt)


@app.post("/api/project/<int:pid>/publish")
@api_login_required
def api_publish(pid):
    """THE MAGIC MOMENT: publishing writes a verified `project.published` credit to FrameVault."""
    db = get_db()
    p = db.execute("SELECT * FROM studio_projects WHERE id=?", (pid,)).fetchone()
    if p is None:
        return jsonify(ok=False, error="Unknown project."), 404
    if p["status"] == "published":
        return jsonify(ok=False, error="Already published."), 409
    me = current_user()
    if not can_edit(membership(db, p["workspace_id"], me["handle"])):
        return jsonify(ok=False, error="Viewers can't publish — ask the workspace owner for editor access."), 403

    db.execute("UPDATE studio_projects SET status='published' WHERE id=?", (pid,))
    ok, detail = credit_framevault(me["handle"], p["name"])
    resp = {"ok": True, "credited": ok}
    resp["note"] = ("Credit written to FrameVault." if ok
                    else f"FrameVault not updated: {detail.get('error','error')}")
    if ok:
        resp["public_url"] = f"{FRAMEVAULT_URL}/@{me['handle']}"
    db.commit()
    return jsonify(resp)


@app.get("/api/search")
def api_search():
    """Read-only search across workspaces and projects, for the command
    palette. Additive endpoint — doesn't touch any existing route."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 1:
        return jsonify(results=[])
    like = f"%{q}%"
    db = get_db()
    results = []
    for w in db.execute(
        "SELECT id, name, owner_name FROM workspaces WHERE name LIKE ? ORDER BY id DESC LIMIT 6",
        (like,),
    ).fetchall():
        results.append({"type": "Workspace", "title": w["name"], "subtitle": "Owned by " + w["owner_name"],
                         "url": f"/workspace/{w['id']}"})
    for p in db.execute(
        "SELECT id, name, status FROM studio_projects WHERE name LIKE ? ORDER BY id DESC LIMIT 6",
        (like,),
    ).fetchall():
        results.append({"type": "Project", "title": p["name"], "subtitle": p["status"].capitalize(),
                         "url": f"/project/{p['id']}"})
    return jsonify(results=results)


@app.get("/__whoami")
def whoami():
    """Identity probe for scripts/check_ports.py — a port can be identified, not guessed."""
    return jsonify(app="OTT Studio", track="CreativeOS", role="creator workspace", port=PORT)


init_db()  # ensure tables exist (also under gunicorn)

if __name__ == "__main__":
    # Port registered in /PORTS.md; override with STUDIO_PORT if you need a scratch instance.
    # HOST defaults to loopback-only; set HOST=0.0.0.0 (see scripts/run_for_phone.py) to reach
    # this from another device on the same network, e.g. a phone.
    app.run(debug=True, host=os.environ.get("HOST", "127.0.0.1"), port=PORT)
