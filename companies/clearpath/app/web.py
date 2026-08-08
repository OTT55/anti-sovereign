"""Web pages a human sees: the route form and the audit log."""

import json

from flask import Blueprint, current_app, jsonify, render_template

from .audit import verify_chain
from .db import get_db

bp = Blueprint("web", __name__)


@bp.get("/")
def index():
    ruleset = current_app.config["RULESET"]
    return render_template(
        "route.html",
        jurisdictions=ruleset.refdata["jurisdictions"],
        asset_types=ruleset.refdata["asset_types"],
        ruleset=ruleset,
    )


@bp.get("/audit")
def audit_page():
    db = get_db()
    rows = db.execute("SELECT * FROM audit ORDER BY id DESC").fetchall()
    entries = [dict(r) for r in rows]
    for e in entries:
        e["payload"] = json.loads(e["payload"])
    chain_ok = verify_chain(list(reversed(entries)))
    return render_template("audit.html", entries=entries, chain_ok=chain_ok)


@bp.get("/__whoami")
def whoami():
    """Identify this app so a port can be confirmed, not guessed — see PORTS.md."""
    return jsonify(
        app=current_app.config.get("APP_NAME", "Clearpath"),
        track="Sovereign Stack",
        port=current_app.config.get("PORT"),
    )
