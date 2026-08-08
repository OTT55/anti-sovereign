"""Answer confidence, derived from retrieval scores already computed — no separate model."""


def assess_confidence(hits):
    """hits: (index, score) pairs sorted desc by score, as returned by retrieval.retrieve().

    top_score alone can mislead: a single strong match and three equally
    strong-but-different matches can share a top_score, so the gap to the
    runner-up is what actually distinguishes "one passage clearly answers
    this" from "the corpus has multiple, possibly conflicting, takes."
    """
    if not hits:
        return {"level": "none", "top_score": 0.0, "gap": 0.0}
    top_score = hits[0][1]
    gap = top_score - hits[1][1] if len(hits) > 1 else top_score
    if top_score >= 0.35 and gap >= 0.08:
        level = "high"
    elif top_score >= 0.15:
        level = "medium"
    else:
        level = "low"
    return {"level": level, "top_score": round(top_score, 3), "gap": round(gap, 3)}
