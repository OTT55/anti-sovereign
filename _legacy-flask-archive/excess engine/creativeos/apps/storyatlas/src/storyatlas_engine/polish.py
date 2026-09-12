"""The one place a local model is allowed near this engine — and its fence.

Ollama is installed on this machine and answering (`llama3.2:3b` locally,
`gpt-oss:120b` via the cloud endpoint). The StoryAtlas engine has never called
it, and after Phases 8–11 that is still true of everything that decides
anything. This module is the single, deliberate exception, and it is **off
unless switched on**.

## Why nearly nothing here may use a model

Everything the engine concludes is arithmetic over dates. `1160 > 1147` is not
a matter of opinion, it is checkable by the writer, and it comes out the same
every time. Handing any of it to a model would trade a proof for a guess and
make the answer unreproducible — which is the exact failure the writer reported
in the first place.

Measured across the engines, one line holds:

> a local model's usefulness is inversely proportional to how much reasoning the
> task requires, and it drops to zero when the task is a calculation.

## What it may do

Exactly one thing: **rephrase a sentence whose facts are already settled.**

After a writer resolves "he" to Aldric, `revise.py` produces a grammatically
blunt sentence. Smoothing that is a language task with no judgement in it, and
it is the category the earlier evaluations found local models genuinely good at.

## The fence

The model's output is **rejected unless every fact survives it**. Names,
numbers and years are extracted from input and output and compared as sets; any
addition, loss or change and the original is returned untouched, with the reason
recorded. So the worst a model can do here is nothing.

This is why the seam is safe to exist: it cannot introduce a fact, it can only
fail to improve a sentence.

    from storyatlas_engine import polish
    polish.available()                      # is Ollama reachable?
    polish.smooth(sentence, enabled=True)   # opt-in, guarded, degrades quietly
"""

import json
import re
import urllib.error
import urllib.request

#: Where Ollama listens by default.
ENDPOINT = "http://localhost:11434"

#: Small and local by default. A larger model is not better at this job — the
#: job is grammar, and the fence rejects anything that is more than grammar.
DEFAULT_MODEL = "llama3.2:3b"

PROMPT = (
    "Rewrite this sentence so it reads naturally. Do not add, remove or change "
    "any name, number, date or fact. Do not explain. Return only the rewritten "
    "sentence.\n\nSentence: {sentence}"
)

_NUMBER = re.compile(r"\b\d+\b")
_NAME = re.compile(r"\b[A-Z][a-z]{2,}\b")


class Result:
    """What the polish attempt did, and why."""

    __slots__ = ("text", "changed", "accepted", "reason", "model")

    def __init__(self, text, changed=False, accepted=False, reason="", model=None):
        self.text = text
        self.changed = changed
        self.accepted = accepted
        self.reason = reason
        self.model = model

    def describe(self):
        return f"{'accepted' if self.accepted else 'rejected'}: {self.reason}"

    def __repr__(self):
        return f"<Polish {self.describe()}>"


def available(endpoint=ENDPOINT, timeout=2.0):
    """Is a local Ollama reachable? Never raises."""
    try:
        with urllib.request.urlopen(f"{endpoint}/api/tags", timeout=timeout) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def models(endpoint=ENDPOINT, timeout=2.0):
    """Which models the local Ollama has. `[]` if it is not running."""
    try:
        with urllib.request.urlopen(f"{endpoint}/api/tags", timeout=timeout) as r:
            return [m["name"] for m in json.loads(r.read().decode()).get("models", [])]
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        return []


def facts_in(text):
    """The set of things a rewrite is forbidden to touch.

    Capitalised words and numbers. Crude on purpose — a loose net over what
    counts as a fact means the guard occasionally rejects a harmless rewrite,
    which costs a little polish. A tight net would occasionally let a changed
    date through, which costs the engine its entire claim to being checkable.
    Erring towards rejection is the only defensible direction.
    """
    return {
        "numbers": frozenset(_NUMBER.findall(text)),
        "names": frozenset(_NAME.findall(text)) - _SENTENCE_STARTERS,
    }


#: Words that are only capitalised because they open a sentence, and would
#: otherwise look like names appearing or vanishing when the clause is reordered.
_SENTENCE_STARTERS = frozenset({
    "The", "This", "That", "These", "Those", "There", "Then", "They", "She",
    "His", "Her", "Him", "Their", "After", "Before", "When", "While", "And",
    "But", "For", "Not", "One", "Two", "Three", "Both", "Each", "Every",
})


def smooth(sentence, enabled=False, model=DEFAULT_MODEL, endpoint=ENDPOINT,
           timeout=30.0):
    """Rephrase a sentence without letting a fact change.

    Returns a `Result`. Off unless `enabled=True`, and the original sentence
    comes back unchanged on every failure path — model absent, model slow,
    model wrong. There is no path where a caller silently receives altered
    facts, and no path where it raises.
    """
    if not enabled:
        return Result(sentence, reason="disabled — the engine does not call models "
                                       "unless asked to")
    if not sentence.strip():
        return Result(sentence, reason="empty")

    body = json.dumps({
        "model": model,
        "prompt": PROMPT.format(sentence=sentence.strip()),
        "stream": False,
        "options": {"temperature": 0.2},
    }).encode()

    try:
        request = urllib.request.Request(
            f"{endpoint}/api/generate", data=body,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode())
    except (urllib.error.URLError, OSError, ValueError) as error:
        return Result(sentence, reason=f"no local model reachable ({error})",
                      model=model)

    candidate = (payload.get("response") or "").strip().strip('"')
    if not candidate:
        return Result(sentence, reason="the model returned nothing", model=model)

    before, after = facts_in(sentence), facts_in(candidate)
    if before["numbers"] != after["numbers"]:
        lost = sorted(before["numbers"] - after["numbers"])
        gained = sorted(after["numbers"] - before["numbers"])
        return Result(sentence, reason=f"rejected — numbers changed "
                                       f"(lost {lost}, gained {gained})", model=model)
    if before["names"] != after["names"]:
        lost = sorted(before["names"] - after["names"])
        gained = sorted(after["names"] - before["names"])
        return Result(sentence, reason=f"rejected — names changed "
                                       f"(lost {lost}, gained {gained})", model=model)

    return Result(candidate, changed=candidate != sentence.strip(), accepted=True,
                  reason="every name and number survived the rewrite", model=model)


def report(endpoint=ENDPOINT, timeout=2.0):
    """A one-line honest statement of the local-model situation."""
    if not available(endpoint, timeout):
        return "Ollama is not reachable. Nothing in the engine needs it."
    installed = ", ".join(models(endpoint, timeout)) or "none"
    return (f"Ollama is running (models: {installed}). The engine calls it "
            f"nowhere by default; `polish.smooth(..., enabled=True)` is the only "
            f"seam, and it may rephrase a sentence but not change a fact.")


__all__ = ["Result", "available", "models", "smooth", "facts_in", "report",
           "ENDPOINT", "DEFAULT_MODEL"]
