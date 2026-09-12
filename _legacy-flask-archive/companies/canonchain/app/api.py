"""
JSON API a machine sees: register a hash, verify a hash.

This is the seam other Sovereign Stack companies will call. Same URLs the MVP
front-end already uses (/register, /api/verify), so the existing pages keep
working unchanged.
"""

from flask import Blueprint, current_app, jsonify, request

from .db import get_db, get_owner
from .registry import (
    DuplicateRegistration, SHA256_RE, all_leaves, find_by_hash, merkle_proof,
    merkle_root, register, registry_size, verify_proof,
)
from .signing import registration_signature_valid

bp = Blueprint("api", __name__)


@bp.post("/register")
def register_route():
    data = request.get_json(silent=True) or {}
    file_hash = (data.get("file_hash") or "").strip().lower()
    filename = (data.get("filename") or "").strip()
    creator_name = (data.get("creator_name") or "").strip()  # display only under V1
    description = (data.get("description") or "").strip()

    if not SHA256_RE.match(file_hash):
        return jsonify(error="Invalid SHA-256 hash."), 400
    if not filename:
        return jsonify(error="Filename is required."), 400

    db = get_db()
    owner = get_owner(db)
    key = current_app.config["SIGNING_KEY"]
    try:
        result = register(
            db, key,
            file_hash=file_hash, filename=filename, description=description,
            creator_id=owner["id"], creator_handle=owner["handle"],
        )
    except DuplicateRegistration as dup:
        e = dup.existing
        return (
            jsonify(
                error="This exact file is already registered.",
                registry_id=e["registry_id"], created_at=e["created_at"],
            ),
            409,
        )

    result["creator_name"] = owner["display_name"]
    return jsonify(result)


@bp.get("/api/stats")
def stats_route():
    """Read-only registry snapshot, for client-side polling — the count and
    root visibly growing live is the point, not decoration. Additive."""
    db = get_db()
    leaves = all_leaves(db)
    return jsonify(count=registry_size(db), root=merkle_root(leaves))


@bp.get("/api/verify")
def verify_route():
    file_hash = (request.args.get("hash") or "").strip().lower()
    if not SHA256_RE.match(file_hash):
        return jsonify(error="Invalid SHA-256 hash."), 400

    db = get_db()
    row = find_by_hash(db, file_hash)
    if not row:
        return jsonify(registered=False)

    owner = db.execute(
        "SELECT * FROM creators WHERE id = ?", (row["creator_id"],)
    ).fetchone()
    leaves = all_leaves(db)
    index = row["leaf_index"]
    root = merkle_root(leaves)
    proof = merkle_proof(leaves, index)
    key = current_app.config["SIGNING_KEY"]

    return jsonify(
        registered=True,
        registry_id=row["registry_id"],
        filename=row["filename"],
        file_hash=row["file_hash"],
        creator_name=owner["display_name"] if owner else "unknown",
        description=row["description"],
        created_at=row["created_at"],
        leaf_index=index,
        registry_size=len(leaves),
        merkle_root=root,
        proof=proof,
        inclusion_verified=verify_proof(file_hash, proof, root),
        signature_valid=registration_signature_valid(
            key, row, owner["handle"] if owner else ""
        ),
    )
