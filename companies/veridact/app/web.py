"""Web pages: enrol a device, authenticate a capture, verify media."""

from flask import Blueprint, current_app, jsonify, render_template

from .crypto import G, P_HEX
from .db import get_db

bp = Blueprint("web", __name__)


@bp.get("/__whoami")
def whoami():
    """Identify this app. Lets anyone (or scripts/check_ports.py) confirm which
    app holds a port, instead of guessing — see PORTS.md."""
    return jsonify(
        app=current_app.config.get("APP_NAME", "Veridact"),
        track="Sovereign Stack",
        port=current_app.config.get("PORT"),
    )


def _ctx(**extra):
    # p_hex / g are injected into the page so the browser crypto uses the same group.
    return dict(p_hex=P_HEX, g=G, **extra)


@bp.get("/")
def index():
    db = get_db()
    count = db.execute("SELECT COUNT(*) AS c FROM devices").fetchone()["c"]
    return render_template("enrol.html", **_ctx(device_count=count))


@bp.get("/api/stats")
def api_stats():
    """Read-only device-enrollment count, for client-side polling — the
    network of enrolled devices growing live, not a static snapshot.
    Additive endpoint."""
    db = get_db()
    count = db.execute("SELECT COUNT(*) AS c FROM devices").fetchone()["c"]
    return jsonify(device_count=count)


@bp.get("/authenticate")
def authenticate_page():
    return render_template("authenticate.html", **_ctx())


@bp.get("/verify")
def verify_page():
    return render_template("verify.html", **_ctx())
