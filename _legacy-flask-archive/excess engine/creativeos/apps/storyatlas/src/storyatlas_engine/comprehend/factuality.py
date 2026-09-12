"""Did it actually happen?

The bug this exists to fix: *"Aldric Vane did **not** die in the year 1147"*
recorded a death. So did *"**If** Aldric had died…"*, *"He **will** die"*, and
*"**Did** Aldric die?"*. A trigger verb was enough, and the words around it that
reverse or suspend its meaning were invisible.

For a continuity engine that is the worst class of error. A missed event leaves
a gap the writer can see; an event the text explicitly *denies* puts a false
fact in the timeline, and every date computed from it, every lifespan bounded by
it, and every contradiction detected against it inherits the mistake.

Four ways a clause can carry a trigger without asserting it:

* **negated** — "did not die", "never returned", "no longer serves"
* **hypothetical** — "if he had died", "would have ended", "suppose she signed"
* **future** — "will die", "is going to sign", "plans to found"
* **interrogative** — "Did Aldric die?"

None are dropped silently. They are marked, kept out of the timeline, and
surfaced to the writer as something to confirm — the same rule as everywhere
else: never assert what the text did not.
"""

import re

ASSERTED = "asserted"
NEGATED = "negated"
HYPOTHETICAL = "hypothetical"
FUTURE = "future"
INTERROGATIVE = "interrogative"

#: Only `asserted` clauses become facts.
FACTUAL = {ASSERTED}

_NEGATION = re.compile(
    r"\b(?:not|n't|never|no longer|nor|neither|without ever|failed to|"
    r"refused to|declined to)\b", re.IGNORECASE)

_HYPOTHETICAL = re.compile(
    r"(?:^|[,;]\s*)\s*(?:if|unless|suppose|imagine|were)\b"
    r"|\b(?:would have|could have|should have|might have|had he|had she|"
    r"had they|were to|about to|nearly|almost)\b", re.IGNORECASE)

_FUTURE = re.compile(
    r"\b(?:will|shall|going to|plans? to|intends? to|expects? to|"
    r"is set to|due to)\b", re.IGNORECASE)

#: A modal makes an event possible rather than actual. Kept separate from
#: future because "may have died" is uncertainty about the past, not a plan.
_MODAL = re.compile(r"\b(?:may|might|could|perhaps|possibly|allegedly|"
                    r"reportedly|rumoured|rumored|supposedly)\b", re.IGNORECASE)


def classify(clause, sentence_text=None):
    """How strongly a clause asserts its event.

    `sentence_text` is used only for the question mark, which lives at the end
    of the sentence and is usually lost by the time a clause is split out.

    Order matters: a question about a negation is still a question, and a
    hypothetical wins over a bare future because "would have" contains neither
    "will" nor a negation but suspends the event completely.
    """
    text = clause or ""
    whole = sentence_text if sentence_text is not None else text

    if whole.strip().endswith("?"):
        return INTERROGATIVE
    if _HYPOTHETICAL.search(text):
        return HYPOTHETICAL
    if _NEGATION.search(text):
        return NEGATED
    if _FUTURE.search(text) or _MODAL.search(text):
        return FUTURE
    return ASSERTED


def is_factual(status):
    return status in FACTUAL


def describe(status):
    return {
        ASSERTED: "stated as fact",
        NEGATED: "explicitly denied",
        HYPOTHETICAL: "hypothetical — it did not happen",
        FUTURE: "future or uncertain, not an established fact",
        INTERROGATIVE: "asked as a question, not stated",
    }[status]
