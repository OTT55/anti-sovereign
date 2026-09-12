"""
Loads a rule pack + its reference data from disk and evaluates a transfer
against them. Pure and DB-free — no import of Flask or sqlite3 anywhere in
this file, so every function here can be unit-tested with plain dicts.

A "ruleset" freezes one rule pack together with the reference-data version it
was written against, so a decision always names exactly what was applied
(decisions/0002). Persisting that frozen pair is db.py's job, not this file's.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .conditions import eval_condition

SEVERITY = {"ALLOW": 0, "REVIEW": 1, "INSUFFICIENT_FACTS": 2, "BLOCK": 3}


@dataclass(frozen=True)
class LoadedRuleset:
    pack: str
    version: str
    content_hash: str
    rules: list
    refdata: dict
    rules_json: str
    refdata_json: str


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def load_ruleset(rulepack_path: Path, refdata_dir: Path) -> LoadedRuleset:
    rules_doc = json.loads(rulepack_path.read_text(encoding="utf-8"))
    refdata_name, refdata_version = rules_doc["refdata"].split("@")
    refdata_path = refdata_dir / f"{refdata_name}.json"
    refdata_doc = json.loads(refdata_path.read_text(encoding="utf-8"))
    if refdata_doc["version"] != refdata_version:
        raise ValueError(
            f"{rulepack_path.name} declares refdata {refdata_name}@{refdata_version}, "
            f"but {refdata_path.name} is version {refdata_doc['version']}."
        )

    rules_json = _canonical(rules_doc)
    refdata_json = _canonical(refdata_doc)
    content_hash = hashlib.sha256((rules_json + refdata_json).encode()).hexdigest()

    return LoadedRuleset(
        pack=rules_doc["pack"], version=rules_doc["version"], content_hash=content_hash,
        rules=rules_doc["rules"], refdata=refdata_doc,
        rules_json=rules_json, refdata_json=refdata_json,
    )


def _context(facts: dict, refdata: dict, params: dict) -> dict:
    names = refdata["jurisdictions"]
    ctx = dict(facts)
    ctx["origin_name"] = names.get(facts.get("origin"), facts.get("origin"))
    ctx["destination_name"] = names.get(facts.get("destination"), facts.get("destination"))
    ctx.update(params)
    return ctx


def evaluate(facts: dict, ruleset: LoadedRuleset) -> tuple[str, list]:
    """Pure: the same facts against the same ruleset always produce the same
    decision — that's what makes a past decision reproducible from the
    ruleset snapshot pinned to it, months after the live rules have moved on.
    """
    findings = []
    for rule in ruleset.rules:
        params = rule.get("params", {})

        # applies_when only ever tests hard facts (asset type, jurisdictions,
        # value), which the API layer guarantees are present — so this always
        # resolves to a real True/False, never "unknown".
        if not eval_condition(rule["applies_when"], facts, ruleset.refdata, params):
            continue

        unknown: list = []
        fires = eval_condition(rule["fires_when"], facts, ruleset.refdata, params, unknown)

        if fires is None:
            missing = ", ".join(sorted(set(unknown)))
            findings.append({
                "outcome": "INSUFFICIENT_FACTS", "rule": rule["rule_id"], "basis": rule["basis"],
                "citation_url": rule.get("citation_url"),
                "message": f"Cannot determine an outcome — not yet known: {missing}.",
                "remediation": f"Provide {missing} before this transfer can be fully routed.",
            })
        elif fires:
            ctx = _context(facts, ruleset.refdata, params)
            findings.append({
                "outcome": rule["outcome"], "rule": rule["rule_id"], "basis": rule["basis"],
                "citation_url": rule.get("citation_url"),
                "message": rule["message"].format(**ctx),
                "remediation": rule["remediation"].format(**ctx) if rule.get("remediation") else None,
            })
        # fires is False: the rule applied and was satisfied — no finding.

    decision = "ALLOW" if not findings else max((f["outcome"] for f in findings), key=lambda o: SEVERITY[o])
    return decision, findings
