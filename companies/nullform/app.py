"""
Nullform — the identity layer (zero-knowledge proof of identity).

Seeds the Sovereign Stack company **Nullform** (identity layer).

Passwords and API keys are shared secrets: to prove you hold one, you send it,
and now two parties know it. Nullform proves identity *without revealing the
secret at all*, using a non-interactive Schnorr zero-knowledge proof over a
2048-bit MODP group (RFC 3526, group 14).

  • Enrolment: the holder generates a private key x **in their browser** and
    publishes only the public key y = g^x mod p. The server stores y as the
    identity anchor and never sees x.

  • Proof: to authenticate, the holder proves knowledge of x for a specific
    message (a challenge / login context) by producing (t, s). The server checks
        g^s  ==  t * y^c  (mod p),   where c = H(g, y, t, message)
    which holds only if the prover knows x — yet x is never transmitted, and the
    proof reveals nothing about x (zero-knowledge). Each proof is bound to its
    message, so proofs cannot be replayed for a different challenge.

Run:  python app.py   →  http://127.0.0.1:5103
"""

import hashlib
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request

DB_PATH = Path(__file__).parent / "nullform.db"

# RFC 3526, 2048-bit MODP Group (id 14). Generator g = 2.
P_HEX = (
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"
    "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
    "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9"
    "DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
    "15728E5A8AACAA68FFFFFFFFFFFFFFFF"
)
P = int(P_HEX, 16)
G = 2
Q = P - 1  # exponents are reduced mod (order divides P-1), so mod P-1 is safe

app = Flask(__name__)


def challenge(y: int, t: int, message: str) -> int:
    """Fiat–Shamir challenge. Must be computed identically in the browser."""
    material = f"{G}|{y}|{t}|{message}".encode()
    return int(hashlib.sha256(material).hexdigest(), 16) % Q


def verify_proof(y: int, t: int, s: int, message: str) -> bool:
    if not (1 <= t < P) or not (0 <= s < Q):
        return False
    c = challenge(y, t, message)
    lhs = pow(G, s, P)
    rhs = (t * pow(y, c, P)) % P
    return lhs == rhs


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS identities (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            identity_id  TEXT NOT NULL UNIQUE,
            handle       TEXT NOT NULL UNIQUE,
            public_key   TEXT NOT NULL,
            created_at   TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@app.route("/")
def index():
    db = get_db()
    count = db.execute("SELECT COUNT(*) c FROM identities").fetchone()["c"]
    return render_template("enroll.html", count=count, p_hex=P_HEX, g=G)


@app.route("/enroll", methods=["POST"])
def enroll():
    data = request.get_json(silent=True) or {}
    handle = (data.get("handle") or "").strip()
    public_key = (data.get("public_key") or "").strip()

    if not handle:
        return jsonify(error="A handle is required."), 400
    try:
        y = int(public_key)
    except ValueError:
        return jsonify(error="Malformed public key."), 400
    if not (1 < y < P):
        return jsonify(error="Public key out of range."), 400

    db = get_db()
    if db.execute("SELECT 1 FROM identities WHERE handle = ?", (handle,)).fetchone():
        return jsonify(error="That handle is already enrolled."), 409

    identity_id = "NF-" + uuid.uuid4().hex[:12].upper()
    created_at = datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT INTO identities (identity_id, handle, public_key, created_at) VALUES (?, ?, ?, ?)",
        (identity_id, handle, public_key, created_at),
    )
    db.commit()
    return jsonify(identity_id=identity_id, handle=handle, created_at=created_at)


@app.route("/prove")
def prove_page():
    return render_template("prove.html", p_hex=P_HEX, g=G)


@app.route("/api/lookup")
def lookup():
    """Return the public key + params a prover needs, given a handle."""
    handle = (request.args.get("handle") or "").strip()
    db = get_db()
    row = db.execute(
        "SELECT identity_id, handle, public_key FROM identities WHERE handle = ?",
        (handle,),
    ).fetchone()
    if not row:
        return jsonify(found=False)
    return jsonify(
        found=True,
        identity_id=row["identity_id"],
        handle=row["handle"],
        public_key=row["public_key"],
        p_hex=P_HEX,
        g=G,
    )


@app.route("/api/verify", methods=["POST"])
def api_verify():
    data = request.get_json(silent=True) or {}
    handle = (data.get("handle") or "").strip()
    message = (data.get("message") or "").strip()
    try:
        t = int(str(data.get("t")))
        s = int(str(data.get("s")))
    except (ValueError, TypeError):
        return jsonify(error="Malformed proof."), 400
    if not message:
        return jsonify(error="A challenge message is required."), 400

    db = get_db()
    row = db.execute(
        "SELECT identity_id, handle, public_key FROM identities WHERE handle = ?",
        (handle,),
    ).fetchone()
    if not row:
        return jsonify(error="No such identity."), 404

    y = int(row["public_key"])
    ok = verify_proof(y, t, s, message)
    return jsonify(
        valid=ok,
        identity_id=row["identity_id"],
        handle=row["handle"],
        message=message,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )


if __name__ == "__main__":
    init_db()
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=5103, debug=True)
