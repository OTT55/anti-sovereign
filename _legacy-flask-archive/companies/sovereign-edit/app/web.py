"""Pages a human sees: the archive, a work's lineage, and identify-a-file."""

from flask import Blueprint, abort, current_app, jsonify, render_template

from .db import get_db
from .util import STEP_TYPES
from .works import get_chain, get_work, list_works, work_summary

bp = Blueprint("web", __name__)


@bp.get("/__whoami")
def whoami():
    """Identify this app so a port can be confirmed, not guessed — see PORTS.md."""
    return jsonify(
        app=current_app.config.get("APP_NAME", "Sovereign Edit"),
        track="Sovereign Stack",
        port=current_app.config.get("PORT"),
    )


@bp.get("/")
def index():
    return render_template("index.html", works=list_works(get_db()))


@bp.get("/works/<work_id>")
def work_page(work_id):
    db = get_db()
    work = get_work(db, work_id)
    if not work:
        abort(404)
    return render_template(
        "work.html",
        work=work,
        summary=work_summary(db, work_id),
        chain=get_chain(db, work_id),
        step_types=[t for t in STEP_TYPES if t != "Registration"],
    )


@bp.get("/identify")
def identify_page():
    return render_template("identify.html")
