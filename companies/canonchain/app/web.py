"""Web pages a human sees: the register page and the verify page."""

from flask import Blueprint, render_template

from .db import get_db
from .registry import all_leaves, merkle_root, registry_size

bp = Blueprint("web", __name__)


@bp.get("/")
def index():
    db = get_db()
    return render_template(
        "register.html",
        count=registry_size(db),
        root=merkle_root(all_leaves(db)),
    )


@bp.get("/verify")
def verify_page():
    return render_template("verify.html")
