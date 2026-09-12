"""
The condition DSL — a tiny, three-valued (Kleene) logic interpreter.

Rules are data (rulepacks/*.json), not code. A condition tree is one of:
    {"and": [cond, ...]} | {"or": [cond, ...]} | {"not": cond}
    {"field": "<fact>", "op": "==|!=|>=|<=|>|<|in|not_in", "value": <literal>}
    {"field": "<fact>", "op": ..., "ref": "<REFDATA_SET_NAME>"}
    {"field": "<fact>", "op": ..., "param": "<rule_param_name>"}
    null  (always true — an empty gate)

Every leaf and combinator returns True, False, or None ("unknown"), using
Kleene's strong three-valued logic instead of Python's two-valued bool:
AND is only False if some operand is False (unknown otherwise propagates);
OR is only True if some operand is True. This is what lets a rule that
touches an unasked fact (e.g. "is PII present?") come back as "can't tell"
instead of silently defaulting to False — see decisions/0004.
"""


def eval_condition(cond: dict | None, facts: dict, refdata: dict, params: dict,
                    unknown_fields: list | None = None) -> bool | None:
    if cond is None:
        return True
    if "and" in cond:
        results = [eval_condition(c, facts, refdata, params, unknown_fields) for c in cond["and"]]
        if any(r is False for r in results):
            return False
        if any(r is None for r in results):
            return None
        return True
    if "or" in cond:
        results = [eval_condition(c, facts, refdata, params, unknown_fields) for c in cond["or"]]
        if any(r is True for r in results):
            return True
        if any(r is None for r in results):
            return None
        return False
    if "not" in cond:
        r = eval_condition(cond["not"], facts, refdata, params, unknown_fields)
        return None if r is None else (not r)
    return _eval_leaf(cond, facts, refdata, params, unknown_fields)


def _eval_leaf(cond: dict, facts: dict, refdata: dict, params: dict,
               unknown_fields: list | None) -> bool | None:
    field = cond["field"]
    op = cond["op"]
    actual = facts.get(field)
    if actual is None:
        if unknown_fields is not None:
            unknown_fields.append(field)
        return None

    if "ref" in cond:
        target = refdata["sets"][cond["ref"]]["members"]
    elif "param" in cond:
        target = params[cond["param"]]
    else:
        target = cond["value"]

    if op == "==":
        return actual == target
    if op == "!=":
        return actual != target
    if op == ">=":
        return actual >= target
    if op == "<=":
        return actual <= target
    if op == ">":
        return actual > target
    if op == "<":
        return actual < target
    if op == "in":
        return actual in target
    if op == "not_in":
        return actual not in target
    raise ValueError(f"Unknown condition operator: {op!r}")
