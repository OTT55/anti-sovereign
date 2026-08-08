"""
Clearpath — compliance routing engine.

Seeds the Sovereign Stack company **Clearpath** (compliance routing).

A cross-border transfer of value or content passes through a thicket of rules:
sanctions, anti-money-laundering thresholds, data-protection transfer
restrictions, data-localization mandates, securities law, content provenance.
Clearpath evaluates a proposed transfer against a transparent rule set and
routes it to one of three outcomes — ALLOW, REVIEW, or BLOCK — with the exact
rules that fired, their legal basis, and any remediations required.

Every decision is written to a hash-chained audit log: each entry commits to the
one before it, so the compliance record is tamper-evident end to end.

Run:  python app.py   →  http://127.0.0.1:5104
"""

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request

DB_PATH = Path(__file__).parent / "clearpath.db"

app = Flask(__name__)

# --------------------------------------------------------------------------
# Reference data
# --------------------------------------------------------------------------
JURISDICTIONS = {
    "US": "United States",
    "EU": "European Union",
    "UK": "United Kingdom",
    "SG": "Singapore",
    "CN": "China",
    "RU": "Russia",
    "IR": "Iran",
    "KP": "North Korea",
}
ASSET_TYPES = ["funds", "security", "crypto", "media", "dataset", "document"]

# Countries under comprehensive sanctions (illustrative, OFAC-style).
SANCTIONED = {"IR", "KP"}
# GDPR "adequacy" destinations that don't need extra transfer safeguards.
GDPR_ADEQUATE = {"UK", "EU"}
# Destinations with strict data-localization regimes.
LOCALIZATION = {"CN", "RU"}

SEVERITY = {"ALLOW": 0, "REVIEW": 1, "BLOCK": 2}


# --------------------------------------------------------------------------
# Rule engine — each rule inspects the transfer and may return a finding.
# A finding = (outcome, rule_name, basis, message, remediation|None)
# --------------------------------------------------------------------------

def rule_sanctions(tx):
    if tx["destination"] in SANCTIONED or tx["origin"] in SANCTIONED:
        who = tx["destination"] if tx["destination"] in SANCTIONED else tx["origin"]
        return ("BLOCK", "Sanctions screening",
                "OFAC comprehensive sanctions",
                f"{JURISDICTIONS[who]} is under comprehensive sanctions; transfers are prohibited.",
                None)
    return None


def rule_aml(tx):
    if tx["asset_type"] in ("funds", "crypto", "security") and tx["value"] >= 10_000:
        if not tx["party_verified"]:
            return ("REVIEW", "AML value threshold",
                    "FATF Rec. 10 / BSA $10k reporting",
                    f"Value ${tx['value']:,.0f} exceeds the $10,000 threshold and the counterparty is unverified.",
                    "Complete KYC / enhanced due diligence on the counterparty.")
    return None


def rule_gdpr(tx):
    if tx["origin"] == "EU" and tx["contains_pii"] and tx["destination"] not in GDPR_ADEQUATE:
        return ("REVIEW", "GDPR restricted transfer",
                "GDPR Art. 44–46",
                f"Personal data is leaving the EU for {JURISDICTIONS[tx['destination']]}, which lacks an adequacy decision.",
                "Attach Standard Contractual Clauses (SCCs) or an equivalent Art. 46 safeguard.")
    return None


def rule_localization(tx):
    if tx["destination"] in LOCALIZATION and (tx["contains_pii"] or tx["asset_type"] == "dataset"):
        return ("REVIEW", "Data localization",
                f"{JURISDICTIONS[tx['destination']]} data-localization law",
                f"{JURISDICTIONS[tx['destination']]} requires covered data to be stored on local infrastructure.",
                "Route storage/processing through an in-country node before transfer.")
    return None


def rule_securities(tx):
    if tx["asset_type"] == "security" and tx["destination"] == "US" and not tx["party_verified"]:
        return ("REVIEW", "Securities offering",
                "SEC Reg D — accredited investor",
                "A security is being transferred to a US counterparty whose accreditation is unverified.",
                "Verify accredited-investor status or use a registered offering.")
    return None


def rule_provenance(tx):
    if tx["asset_type"] == "media" and not tx["provenance_attached"]:
        return ("REVIEW", "Content provenance",
                "Sovereign Stack provenance policy",
                "Media is being routed without a provenance attestation, so its origin cannot be verified downstream.",
                "Attach a Canonchain registration or Veridact manifest before release.")
    return None


RULES = [rule_sanctions, rule_aml, rule_gdpr, rule_localization, rule_securities, rule_provenance]


def evaluate(tx):
    findings = []
    for rule in RULES:
        f = rule(tx)
        if f:
            outcome, name, basis, message, remediation = f
            findings.append({
                "outcome": outcome, "rule": name, "basis": basis,
                "message": message, "remediation": remediation,
            })
    if not findings:
        decision = "ALLOW"
    else:
        decision = max((f["outcome"] for f in findings), key=lambda o: SEVERITY[o])
    return decision, findings


# --------------------------------------------------------------------------
# Database + hash-chained audit log
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
        CREATE TABLE IF NOT EXISTS audit (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id     TEXT NOT NULL UNIQUE,
            created_at  TEXT NOT NULL,
            payload     TEXT NOT NULL,
            prev_hash   TEXT NOT NULL,
            entry_hash  TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def append_audit(db, case_id, created_at, payload):
    last = db.execute("SELECT entry_hash FROM audit ORDER BY id DESC LIMIT 1").fetchone()
    prev_hash = last["entry_hash"] if last else "0" * 64
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    entry_hash = hashlib.sha256((prev_hash + body).encode()).hexdigest()
    db.execute(
        "INSERT INTO audit (case_id, created_at, payload, prev_hash, entry_hash) VALUES (?, ?, ?, ?, ?)",
        (case_id, created_at, body, prev_hash, entry_hash),
    )
    db.commit()
    return prev_hash, entry_hash


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("route.html", jurisdictions=JURISDICTIONS, asset_types=ASSET_TYPES)


@app.route("/evaluate", methods=["POST"])
def evaluate_route():
    data = request.get_json(silent=True) or {}
    try:
        tx = {
            "asset_type": data["asset_type"],
            "value": float(data.get("value") or 0),
            "origin": data["origin"],
            "destination": data["destination"],
            "contains_pii": bool(data.get("contains_pii")),
            "party_verified": bool(data.get("party_verified")),
            "provenance_attached": bool(data.get("provenance_attached")),
        }
    except (KeyError, ValueError):
        return jsonify(error="Incomplete transfer description."), 400
    if tx["asset_type"] not in ASSET_TYPES or tx["origin"] not in JURISDICTIONS or tx["destination"] not in JURISDICTIONS:
        return jsonify(error="Unknown asset type or jurisdiction."), 400

    decision, findings = evaluate(tx)
    case_id = "CP-" + uuid.uuid4().hex[:12].upper()
    created_at = datetime.now(timezone.utc).isoformat()
    payload = {"case_id": case_id, "tx": tx, "decision": decision, "findings": findings}

    db = get_db()
    prev_hash, entry_hash = append_audit(db, case_id, created_at, payload)

    return jsonify(
        case_id=case_id, created_at=created_at, decision=decision,
        findings=findings, tx=tx, prev_hash=prev_hash, entry_hash=entry_hash,
    )


@app.get("/api/audit/search")
def api_audit_search():
    """Read-only search over case IDs, for the command palette. Additive
    endpoint — doesn't touch any existing route."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 1:
        return jsonify(results=[])
    db = get_db()
    rows = db.execute(
        "SELECT case_id, created_at, payload FROM audit WHERE case_id LIKE ? ORDER BY id DESC LIMIT 8",
        (f"%{q}%",),
    ).fetchall()
    results = []
    for r in rows:
        payload = json.loads(r["payload"])
        results.append({
            "case_id": r["case_id"],
            "subtitle": f"{payload['decision']} · {payload['tx']['asset_type']} · {r['created_at'][:10]}",
        })
    return jsonify(results=results)


@app.get("/api/audit/latest")
def api_audit_latest():
    """Read-only: the most recent audit entries, for client-side polling so
    the log feels alive — a decision made elsewhere appears without a
    refresh. Additive endpoint."""
    limit = min(int(request.args.get("limit") or 5), 20)
    db = get_db()
    rows = db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    entries = [dict(r) for r in rows]
    for e in entries:
        e["payload"] = json.loads(e["payload"])
    total = db.execute("SELECT COUNT(*) c FROM audit").fetchone()["c"]
    return jsonify(entries=entries, total=total)


@app.route("/audit")
def audit_page():
    db = get_db()
    rows = db.execute("SELECT * FROM audit ORDER BY id DESC").fetchall()
    entries = [dict(r) for r in rows]
    for e in entries:
        e["payload"] = json.loads(e["payload"])
    # verify chain integrity
    chain_ok = True
    ordered = list(reversed(entries))
    prev = "0" * 64
    for e in ordered:
        body = json.dumps(e["payload"], sort_keys=True, separators=(",", ":"))
        if e["prev_hash"] != prev or hashlib.sha256((prev + body).encode()).hexdigest() != e["entry_hash"]:
            chain_ok = False
            break
        prev = e["entry_hash"]
    return render_template("audit.html", entries=entries, chain_ok=chain_ok)


if __name__ == "__main__":
    init_db()
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=5104, debug=True)
