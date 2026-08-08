"""Phase 10 — an interactive revision session, and a refined draft out the end.

Two things were asked for and they are really one thing:

> *"It should have an option to produce you not even a draft, but a refined
> version. And the tweaking should be interactive."*

A one-shot "cleaned up draft" is the wrong shape for this. Almost every
contradiction has more than one honest resolution — a character on the page
after their death is either a wrong death date, a wrong scene date, or a
deliberate flashback, and **nothing in the text distinguishes them.** A tool
that picks one has invented a fact, which is precisely what this engine exists
not to do.

So the loop is: the engine finds and ranks, the writer decides, the engine
applies the decision and *re-reads the whole draft from scratch*. That last part
is the design. It is slower than patching the model in place, and it is the only
way to answer the question that actually matters after any edit:

> **what did that just break?**

A revision that fixes one contradiction and quietly creates two is worse than no
revision. `preview()` shows both sides before anything is committed, so a
decision is made with its consequences visible.

This is the agentic shape without the agent: propose, preview, apply, re-check,
undo. The judgement stays with the writer; the bookkeeping — which is what a
writer actually cannot do by hand across a 90,000-word draft — is the engine's.

Nothing here calls a model, and the refined draft is the writer's own words with
their own decisions folded in.
"""

import difflib
import re

from .intelligence import analyse
from .worklist import worklist

#: Pronouns a `name` action will replace, longest first so "himself" is not
#: matched as "him".
PRONOUNS = ("themselves", "himself", "herself", "their", "them", "hers", "his",
            "her", "him", "they", "she", "he", "it")

_YEAR = re.compile(r"\b(\d{3,4})\b")


class Decision:
    """One choice the writer made, kept so the session can be replayed."""

    __slots__ = ("fix_id", "rule", "action", "value", "before", "after", "note",
                 "dismissed_key")

    def __init__(self, fix_id, rule, action, value=None, before="", after="",
                 note="", dismissed_key=None):
        self.fix_id = fix_id
        self.rule = rule
        self.action = action
        self.value = value
        self.before = before
        self.after = after
        self.note = note
        #: The exact key this decision suppressed, so `undo()` can lift exactly
        #: that suppression rather than guessing at it.
        self.dismissed_key = dismissed_key

    def describe(self):
        detail = f" → {self.value}" if self.value is not None else ""
        return f"{self.fix_id} [{self.rule}] {self.action.label}{detail}"

    def __repr__(self):
        return f"<Decision {self.describe()}>"


class Preview:
    """What a decision would do, before it is made."""

    __slots__ = ("text", "diff", "resolved", "introduced", "unchanged",
                 "before_summary", "after_summary", "action")

    def __init__(self, text, diff, resolved, introduced, unchanged,
                 before_summary, after_summary, action=None):
        self.text = text
        self.diff = diff
        #: Findings that were present and are now gone.
        self.resolved = resolved
        #: Findings this edit created. The number that decides whether an edit
        #: is an improvement.
        self.introduced = introduced
        self.unchanged = unchanged
        self.before_summary = before_summary
        self.after_summary = after_summary
        self.action = action

    @property
    def is_improvement(self):
        return len(self.resolved) > len(self.introduced)

    def describe(self):
        verdict = ("an improvement" if self.is_improvement
                   else "no better" if len(self.resolved) == len(self.introduced)
                   else "worse")
        return (f"{len(self.resolved)} resolved, {len(self.introduced)} "
                f"introduced — {verdict}")

    def render(self):
        lines = [f"## Preview: {self.describe()}", ""]
        if self.diff:
            lines += ["```diff", self.diff.rstrip(), "```", ""]
        if self.resolved:
            lines.append("Resolved:")
            lines += [f"  - {t}" for _k, t in self.resolved]
            lines.append("")
        if self.introduced:
            lines.append("Introduced:")
            lines += [f"  ! {t}" for _k, t in self.introduced]
            lines.append("")
        return "\n".join(lines).strip()

    def __repr__(self):
        return f"<Preview {self.describe()}>"


class Session:
    """An interactive revision of one draft.

    ```python
    session = Session(draft)
    for fix in session.issues()[:3]:
        print(fix.describe())

    fix = session.issues()[0]
    print(session.preview(fix, fix.options[0], value=1150).render())
    session.apply(fix, fix.options[0], value=1150)
    print(session.refined())
    ```
    """

    def __init__(self, text, known_names=None, era_label="Year"):
        self.original = text
        self.text = text
        self.known_names = known_names
        self.era_label = era_label
        self.history = []
        self._dismissed = set()
        self._reread()

    # -- state -------------------------------------------------------------

    def _reread(self):
        self.report = analyse(self.text, known_names=self.known_names,
                              era_label=self.era_label)
        self.reading = self.report.reading

    def issues(self, limit=None):
        """The ranked worklist, minus anything dismissed."""
        fixes = [f for f in worklist(self.report)
                 if _key(f.rule, f.subject, f.title) not in self._dismissed]
        for i, fix in enumerate(fixes):
            fix.id = f"F{i + 1:02d}"
        return fixes[:limit] if limit else fixes

    def summary(self):
        counts = {}
        for fix in self.issues():
            counts[fix.severity] = counts.get(fix.severity, 0) + 1
        return counts

    # -- the loop ----------------------------------------------------------

    def preview(self, fix, action, value=None):
        """What this decision would do. Changes nothing.

        The re-read is a full re-read, not an incremental patch. Anything less
        cannot answer "what did that break", because the breakage is usually
        somewhere the edit does not touch — a date three paragraphs later that
        was computed from the one just changed.
        """
        text = self._edited(action, value)
        before = self._findings(self.report)
        after_report = analyse(text, known_names=self.known_names,
                               era_label=self.era_label)
        after = self._findings(after_report)

        before_keys = {k for k, _t in before}
        after_keys = {k for k, _t in after}

        return Preview(
            text=text,
            diff=_diff(self.text, text),
            resolved=[(k, t) for k, t in before if k not in after_keys],
            introduced=[(k, t) for k, t in after if k not in before_keys],
            unchanged=[(k, t) for k, t in after if k in before_keys],
            before_summary=self.report.summary(),
            after_summary=after_report.summary(),
            action=action,
        )

    def apply(self, fix, action, value=None):
        """Commit a decision, re-read, and return the resulting `Preview`."""
        preview = self.preview(fix, action, value)
        before = self.text
        self.text = preview.text

        dismissed_key = None
        if action.kind == "dismiss":
            dismissed_key = _key(fix.rule, fix.subject, fix.title)
            self._dismissed.add(dismissed_key)

        self.history.append(Decision(
            fix_id=fix.id, rule=fix.rule, action=action, value=value,
            before=before, after=self.text, note=preview.describe(),
            dismissed_key=dismissed_key,
        ))
        self._reread()
        return preview

    def undo(self):
        """Step back one decision. Returns the decision undone, or `None`."""
        if not self.history:
            return None
        decision = self.history.pop()
        self.text = decision.before
        if decision.dismissed_key is not None:
            self._dismissed.discard(decision.dismissed_key)
        self._reread()
        return decision

    def reset(self):
        self.text = self.original
        self.history.clear()
        self._dismissed.clear()
        self._reread()

    # -- output ------------------------------------------------------------

    def refined(self):
        """The draft with every applied decision folded in.

        The writer's own prose. Pronouns resolved where they said so, dates made
        explicit where they gave one, deliberate anomalies marked as deliberate.
        Not a rewrite — a version where what was ambiguous has been settled by
        the person entitled to settle it.
        """
        return self.text

    def diff(self):
        """Everything that changed across the whole session."""
        return _diff(self.original, self.text, "original", "refined")

    def transcript(self):
        """The decision log — what was changed, and what each change did."""
        if not self.history:
            return "No decisions made."
        lines = ["# Revision log", ""]
        for i, decision in enumerate(self.history):
            lines.append(f"{i + 1}. {decision.describe()}")
            lines.append(f"     {decision.note}")
        return "\n".join(lines)

    # -- text surgery ------------------------------------------------------

    def _edited(self, action, value):
        """Apply one action to the text and return the new text.

        Operates on the sentence's recorded source offsets rather than by
        searching for its text, because the same sentence can legitimately occur
        twice in a draft and a search would edit whichever came first.
        """
        if action.kind in ("accept", "dismiss", "confirm-type"):
            return self.text

        index = action.sentence_index
        if index is None or index >= len(self.reading.sentences):
            return self.text

        sentence = self.reading.sentences[index]
        original = self.text[sentence.start:sentence.end]

        if action.kind == "set-year":
            if value is None:
                return self.text
            replaced = _YEAR.sub(str(value), original, count=1)
            if replaced == original:            # no year to replace — state one
                replaced = _append_clause(original, f"in {self.era_label} {value}")
            new = replaced

        elif action.kind == "name":
            name = (action.payload or {}).get("name") or value
            if not name:
                return self.text
            new = _replace_pronoun(original, name)

        elif action.kind == "annotate":
            note = (action.payload or {}).get("note") or value or "confirmed"
            new = _append_note(original, note)

        elif action.kind == "strike":
            new = ""

        elif action.kind == "record-death":
            if value is None:
                return self.text
            subject = (action.payload or {}).get("name", "")
            new = original + f" {subject} died in {self.era_label} {value}."

        else:
            return self.text

        return self.text[:sentence.start] + new + self.text[sentence.end:]

    @staticmethod
    def _findings(report):
        """A stable identity for every finding, so two reports can be compared.

        Keyed on rule, subject and wording rather than on sentence index —
        indices shift when a sentence is struck, and a finding that merely moved
        would otherwise look like one resolved and one created.
        """
        out = []
        for violation in report.violations:
            out.append((_key(violation.rule, violation.subject, violation.text),
                        violation.text))
        for question in report.reading.questions:
            out.append((_key(question.kind, question.about, question.text),
                        question.text))
        return out


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _key(rule, subject, text):
    return (rule, subject or "", re.sub(r"\d+", "#", text or "")[:80])


def _append_clause(sentence, clause):
    """Add a trailing clause before the sentence's final punctuation."""
    match = re.search(r"([.!?]+[\"'”’)\]]*)\s*$", sentence)
    if match:
        return sentence[:match.start()] + f", {clause}" + match.group(1)
    return f"{sentence}, {clause}"


def _append_note(sentence, note):
    """Add a bracketed note *inside* the sentence, before its final stop.

    Bracketed rather than woven in: the writer's sentence is left exactly as
    written, and the annotation is visibly the engine's. Rewriting someone's
    prose to record a decision about it is not the engine's business.

    Inside the sentence rather than after it, because a note placed after the
    full stop belongs to the *next* sentence as far as the splitter is
    concerned — so a marker meant to exempt one line silently exempts the line
    below it and leaves the real one still reported.
    """
    sentence = sentence.rstrip()
    match = re.search(r"([.!?]+[\"'”’)\]]*)\s*$", sentence)
    if match:
        return f"{sentence[:match.start()]} [{note}]{match.group(1)}"
    return f"{sentence} [{note}]"


def _replace_pronoun(sentence, name):
    """Replace the first pronoun with a name, keeping the sentence's shape."""
    for pronoun in PRONOUNS:
        pattern = re.compile(rf"\b{pronoun}\b", re.IGNORECASE)
        match = pattern.search(sentence)
        if match:
            return sentence[:match.start()] + name + sentence[match.end():]
    return sentence


def _diff(before, after, from_label="before", to_label="after"):
    if before == after:
        return ""
    return "".join(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile=from_label, tofile=to_label, n=1))


__all__ = ["Session", "Preview", "Decision"]
