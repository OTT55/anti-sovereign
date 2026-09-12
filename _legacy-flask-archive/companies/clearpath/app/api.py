"""
JSON API a machine sees: route a transfer, plus the read-only audit queries
the front-end's command palette and live-poll already call. (The MVP's
templates shipped calling `/api/audit/latest` and `/api/audit/search`, but
the MVP's app.py never defined them — every such request 404'd silently. Both
are implemented for real here.)
"""

import json

from flask import Blueprint, current_app, jsonify, request

from .audit import append_entry
from .db import get_db
from .rules import evaluate
from .util import new_case_id, now_iso

bp = Blueprint("api", __name__)

TRI_STATE_FIELDS = ("contains_pii", "party_verified", "provenance_attached")


def _tri_state(data: dict, field: str):
    """True / False / None("unknown"). None means the caller didn't say —
    a real, distinct answer, not an absence that should read as "no"."""
    value = data.get(field)
    if value is None or isinstance(value, bool):
        return value
    raise ValueError(f"{field} must be true, false, or omitted.")


@bp.post("/evaluate")
def evaluate_route():
    data = request.get_json(silent=True) or {}
    ruleset = current_app.config["RULESET"]
    try:
        facts = {
            "asset_type": data["asset_type"],
            "value": float(data.get("value") or 0),
            "origin": data["origin"],
            "destination": data["destination"],
            **{f: _tri_state(data, f) for f in TRI_STATE_FIELDS},
        }
    except (KeyError, ValueError, TypeError):
        return jsonify(error="Incomplete or malformed transfer description."), 400

    refdata = ruleset.refdata
    if (facts["asset_type"] not in refdata["asset_types"]
            or facts["origin"] not in refdata["jurisdictions"]
            or facts["destination"] not in refdata["jurisdictions"]):
        return jsonify(error="Unknown asset type or jurisdiction."), 400

    decision, findings = evaluate(facts, ruleset)

    case_id = new_case_id()
    created_at = now_iso()
    payload = {"case_id": case_id, "facts": facts, "decision": decision, "findings": findings}

    db = get_db()
    prev_hash, entry_hash = append_entry(
        db, case_id, created_at, current_app.config["RULESET_ID"], payload
    )

    return jsonify(
        case_id=case_id, created_at=created_at, decision=decision, findings=findings,
        facts=facts, ruleset_pack=ruleset.pack, ruleset_version=ruleset.version,
        prev_hash=prev_hash, entry_hash=entry_hash,
    )


@bp.get("/api/audit/latest")
def audit_latest():
    """Read-only tail of the log, for the audit page's live poll — the count
    and newest entries visibly growing is the point, not decoration."""
    limit = min(max(request.args.get("limit", 5, type=int), 1), 50)
    db = get_db()
    total = db.execute("SELECT COUNT(*) AS n FROM audit").fetchone()["n"]
    rows = db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    entries = [dict(r) for r in rows]
    for e in entries:
        e["payload"] = json.loads(e["payload"])
    return jsonify(total=total, entries=entries)


@bp.get("/api/audit/search")
def audit_search():
    """Case-id substring search behind the command palette (Ctrl/Cmd+K)."""
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify(results=[])
    db = get_db()
    rows = db.execute(
        "SELECT case_id, payload FROM audit WHERE case_id LIKE ? ORDER BY id DESC LIMIT 8",
        (f"%{q}%",),
    ).fetchall()
    results = []
    for r in rows:
        payload = json.loads(r["payload"])
        facts = payload.get("facts", {})
        subtitle = (f"{payload.get('decision')} · {facts.get('asset_type', '')} · "
                    f"{facts.get('origin', '')} → {facts.get('destination', '')}")
        results.append({"case_id": r["case_id"], "subtitle": subtitle})
    return jsonify(results=results)
