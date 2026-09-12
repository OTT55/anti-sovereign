"""JSON API — how machines (and the pages' JS) talk to Sovereign Edit."""

from flask import Blueprint, jsonify, request

from .db import get_db
from .works import BadInput, append_step, create_work, identify, set_master

bp = Blueprint("api", __name__)


@bp.post("/works")
def create_work_route():
    data = request.get_json(silent=True) or {}
    try:
        work_id = create_work(
            get_db(),
            title=(data.get("title") or ""),
            director=(data.get("director") or ""),
        )
    except BadInput as e:
        return jsonify(error=str(e)), 400
    return jsonify(work_id=work_id)


@bp.post("/works/<work_id>/steps")
def add_step_route(work_id):
    db = get_db()
    if not db.execute("SELECT 1 FROM works WHERE work_id = ?", (work_id,)).fetchone():
        return jsonify(error="Unknown work."), 404
    data = request.get_json(silent=True) or {}
    try:
        bh = append_step(
            db, work_id,
            step_type=(data.get("step_type") or ""),
            actor=(data.get("actor") or ""),
            tool=(data.get("tool") or ""),
            notes=(data.get("notes") or ""),
            filename=(data.get("filename") or ""),
            file_hash=(data.get("file_hash") or ""),
        )
    except BadInput as e:
        return jsonify(error=str(e)), 400
    return jsonify(ok=True, block_hash=bh)


@bp.post("/works/<work_id>/master")
def set_master_route(work_id):
    data = request.get_json(silent=True) or {}
    try:
        set_master(get_db(), work_id, int(data.get("seq")))
    except (TypeError, ValueError):
        return jsonify(error="A step number is required."), 400
    except BadInput as e:
        return jsonify(error=str(e)), 400
    return jsonify(ok=True)


@bp.get("/api/identify")
def identify_route():
    try:
        return jsonify(identify(get_db(), request.args.get("hash") or ""))
    except BadInput as e:
        return jsonify(error=str(e)), 400
