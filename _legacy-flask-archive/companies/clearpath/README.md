# Clearpath — Compliance Routing

**Sovereign Stack company #3 · Category: Compliance Routing**

Clearpath is a compliance routing engine. A single cross-border transfer of value
or content can touch sanctions law, anti-money-laundering thresholds,
data-protection transfer rules, data-localization mandates, securities
regulation, and content-provenance policy at once. Clearpath evaluates a proposed
transfer against a transparent rule set and routes it to one of three outcomes —
**ALLOW**, **REVIEW**, or **BLOCK** — showing exactly which rules fired, their
legal basis, and what must be remediated.

## The rule set (MVP)

| Rule | Basis | Fires when |
|------|-------|-----------|
| Sanctions screening | OFAC comprehensive sanctions | Origin or destination is a sanctioned jurisdiction → **BLOCK** |
| AML value threshold | FATF Rec. 10 / BSA | Funds/crypto/security ≥ $10,000 with an unverified counterparty → **REVIEW** |
| GDPR restricted transfer | GDPR Art. 44–46 | PII leaving the EU to a non-adequate country → **REVIEW** |
| Data localization | Local law (CN/RU) | PII or datasets bound for a localization regime → **REVIEW** |
| Securities offering | SEC Reg D | A security sent to an unverified US counterparty → **REVIEW** |
| Content provenance | Sovereign Stack policy | Media routed with no provenance attestation → **REVIEW** |

The final decision is the highest severity among the rules that fired
(`BLOCK > REVIEW > ALLOW`). Rules are ordinary Python functions in
[`app.py`](app.py) — auditable, testable, and easy to extend.

## Tamper-evident audit log

Every decision is appended to a hash-chained log. Each entry stores the hash of
the previous entry and its own hash over `SHA-256(prev_hash + decision_body)`.
Altering or deleting any past decision changes its hash and breaks every link
after it — the **Audit log** page recomputes the whole chain and reports whether
it is intact.

## How to run locally

```bash
cd companies/clearpath
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5104>.

Try these to see each outcome:
- **BLOCK** — destination `Iran (IR)`.
- **REVIEW** — asset `funds`, value `50000`, counterparty *not* verified (AML); or
  origin `EU`, `media`/`dataset` with **Contains PII** to a non-EU destination.
- **ALLOW** — `document`, `US → SG`, no PII, verified counterparty.

Then open the **Audit log** to see the chained record and its integrity check.

## Stack

- Backend: Python Flask + SQLite; rule engine and hash chain use only the stdlib
- Frontend: hand-written HTML/CSS/JS, no frameworks
