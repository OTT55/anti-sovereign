"""
Strata Finance — capital settlement via revenue waterfalls.

Seeds the Sovereign Stack company **Strata Finance** (capital settlement).

Revenue rarely splits evenly. A film or IP deal pays out through a *waterfall*:
a distribution fee comes off the top, investors recoup their principal, and only
then does the remaining "backend" split among the participants. Strata Finance
lets you define that waterfall as ordered tiers and then settle real payments
through it. Every settlement runs the tiers deterministically in integer cents
(no floating-point drift) and produces a double-entry ledger: the gross received
always equals the sum distributed.

Recoupment is stateful — each recoupment tier remembers how much it has already
been paid across settlements, so caps deplete correctly over time.

Run:  python app.py   →  http://127.0.0.1:5106
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, g, jsonify, render_template, request

DB_PATH = Path(__file__).parent / "strata.db"

app = Flask(__name__)


# --------------------------------------------------------------------------
# Waterfall engine (all math in integer cents)
# --------------------------------------------------------------------------

def run_waterfall(tiers, recouped_cents, gross_cents):
    """Distribute `gross_cents` through the tiers.

    tiers: list of dicts:
      {"kind": "fee",    "party": str, "percent": float}    # % of gross, off the top
      {"kind": "recoup", "party": str, "cap_cents": int}    # up to remaining cap
      {"kind": "split",  "weights": {party: percent}}       # % of what remains
    recouped_cents: list parallel to tiers; cumulative cents already paid to each
                    recoup tier (ignored for non-recoup tiers).

    Returns (line_items, new_recouped, holdback_cents).
    Each line item: {"tier_index", "tier_label", "party", "amount_cents"}.
    """
    pool = gross_cents
    lines = []
    new_recouped = list(recouped_cents)

    for i, tier in enumerate(tiers):
        if pool <= 0:
            break
        kind = tier["kind"]
        if kind == "fee":
            take = min(pool, round(gross_cents * tier["percent"] / 100))
            if take > 0:
                lines.append({"tier_index": i, "tier_label": f"Fee — {tier['party']} ({tier['percent']}%)",
                              "party": tier["party"], "amount_cents": take})
                pool -= take
        elif kind == "recoup":
            remaining = max(0, tier["cap_cents"] - new_recouped[i])
            take = min(pool, remaining)
            if take > 0:
                new_recouped[i] += take
                lines.append({"tier_index": i, "tier_label": f"Recoupment — {tier['party']}",
                              "party": tier["party"], "amount_cents": take})
                pool -= take
        elif kind == "split":
            weights = tier["weights"]
            parties = list(weights.items())
            distributed = 0
            # floor each share; last participant absorbs the rounding remainder
            for j, (party, pct) in enumerate(parties):
                if j == len(parties) - 1:
                    share = pool - distributed
                else:
                    share = pool * pct // 100
                    distributed += share
                if share > 0:
                    lines.append({"tier_index": i, "tier_label": "Backend split",
                                  "party": party, "amount_cents": share})
            pool = 0
    return lines, new_recouped, pool


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
        """CREATE TABLE IF NOT EXISTS deals (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            deal_id    TEXT NOT NULL UNIQUE,
            name       TEXT NOT NULL,
            tiers      TEXT NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS settlements (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            settlement_id TEXT NOT NULL UNIQUE,
            deal_id       TEXT NOT NULL,
            gross_cents   INTEGER NOT NULL,
            holdback_cents INTEGER NOT NULL,
            lines         TEXT NOT NULL,
            created_at    TEXT NOT NULL
        )"""
    )
    conn.commit()
    conn.close()


def load_deal(db, deal_id):
    row = db.execute("SELECT * FROM deals WHERE deal_id = ?", (deal_id,)).fetchone()
    if not row:
        return None
    tiers = json.loads(row["tiers"])
    return {"deal_id": row["deal_id"], "name": row["name"], "tiers": tiers, "created_at": row["created_at"]}


def current_recouped(db, deal_id, tiers):
    """Sum recoupment already paid per tier across all past settlements."""
    recouped = [0] * len(tiers)
    rows = db.execute("SELECT lines FROM settlements WHERE deal_id = ?", (deal_id,)).fetchall()
    for r in rows:
        for ln in json.loads(r["lines"]):
            i = ln["tier_index"]
            if i < len(tiers) and tiers[i]["kind"] == "recoup":
                recouped[i] += ln["amount_cents"]
    return recouped


def party_totals(lines_list):
    totals = {}
    for lines in lines_list:
        for ln in lines:
            totals[ln["party"]] = totals.get(ln["party"], 0) + ln["amount_cents"]
    return totals


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def validate_tiers(tiers):
    if not isinstance(tiers, list) or not tiers:
        return "Define at least one waterfall tier."
    for t in tiers:
        k = t.get("kind")
        if k == "fee":
            if not t.get("party") or not (0 < float(t.get("percent", 0)) <= 100):
                return "Fee tiers need a party and a percent in (0, 100]."
        elif k == "recoup":
            if not t.get("party") or float(t.get("cap_cents", 0)) <= 0:
                return "Recoupment tiers need a party and a positive cap."
        elif k == "split":
            w = t.get("weights") or {}
            if not w:
                return "Split tiers need at least one participant."
            if round(sum(float(v) for v in w.values())) != 100:
                return "Split percentages must sum to 100."
        else:
            return f"Unknown tier kind: {k}"
    return None


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@app.route("/")
def index():
    db = get_db()
    deals = db.execute("SELECT * FROM deals ORDER BY id DESC").fetchall()
    return render_template("index.html", deals=deals)


@app.route("/deals", methods=["POST"])
def create_deal():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    tiers = data.get("tiers")
    if not name:
        return jsonify(error="Deal name is required."), 400
    err = validate_tiers(tiers)
    if err:
        return jsonify(error=err), 400
    deal_id = "SF-" + uuid.uuid4().hex[:10].upper()
    db = get_db()
    db.execute(
        "INSERT INTO deals (deal_id, name, tiers, created_at) VALUES (?, ?, ?, ?)",
        (deal_id, name, json.dumps(tiers), datetime.now(timezone.utc).isoformat()),
    )
    db.commit()
    return jsonify(deal_id=deal_id)


@app.route("/deals/<deal_id>")
def deal_page(deal_id):
    db = get_db()
    deal = load_deal(db, deal_id)
    if not deal:
        abort(404)
    settlements = db.execute(
        "SELECT * FROM settlements WHERE deal_id = ? ORDER BY id DESC", (deal_id,)
    ).fetchall()
    settlements = [dict(s) for s in settlements]
    for s in settlements:
        s["lines"] = json.loads(s["lines"])
    recouped = current_recouped(db, deal_id, deal["tiers"])
    totals = party_totals([s["lines"] for s in settlements])
    return render_template("deal.html", deal=deal, settlements=settlements,
                           recouped=recouped, totals=totals)


@app.route("/deals/<deal_id>/settle", methods=["POST"])
def settle(deal_id):
    db = get_db()
    deal = load_deal(db, deal_id)
    if not deal:
        return jsonify(error="Unknown deal."), 404
    data = request.get_json(silent=True) or {}
    try:
        gross_cents = round(float(data.get("amount")) * 100)
    except (TypeError, ValueError):
        return jsonify(error="Enter a valid amount."), 400
    if gross_cents <= 0:
        return jsonify(error="Amount must be positive."), 400

    recouped = current_recouped(db, deal_id, deal["tiers"])
    lines, _new, holdback = run_waterfall(deal["tiers"], recouped, gross_cents)

    # double-entry invariant: everything distributed + holdback == gross
    assert sum(ln["amount_cents"] for ln in lines) + holdback == gross_cents

    settlement_id = "STL-" + uuid.uuid4().hex[:10].upper()
    db.execute(
        """INSERT INTO settlements (settlement_id, deal_id, gross_cents, holdback_cents, lines, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (settlement_id, deal_id, gross_cents, holdback, json.dumps(lines),
         datetime.now(timezone.utc).isoformat()),
    )
    db.commit()
    return jsonify(
        settlement_id=settlement_id,
        gross_cents=gross_cents,
        holdback_cents=holdback,
        lines=lines,
    )


@app.route("/__whoami")
def whoami():
    return jsonify({
        "name": "Strata Finance",
        "port": 5106,
        "category": "Capital Settlement",
        "status": "operational"
    })


if __name__ == "__main__":

    init_db()
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=5106, debug=True)
