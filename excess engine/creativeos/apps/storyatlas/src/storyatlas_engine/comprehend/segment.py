"""Sentence segmentation that survives fiction.

Naive `split on [.!?]` breaks on the things prose is full of — "Dr.", "St.
Aldric", an initial like "J. Varo", an ellipsis, a quotation mark after the
stop. Every one of those produces a fragment that later stages then try to read
as an event, so the errors compound. Getting this right first is cheaper than
filtering rubbish out of every stage downstream.
"""

import re

#: Abbreviations that end in a period without ending a sentence.
ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "st", "lt", "capt", "sgt", "gen", "col", "sr", "jr",
    "prof", "rev", "hon", "adm", "cmdr", "maj", "fr", "no", "vs", "etc", "al",
}

_SENTENCE_END = re.compile(r'([.!?]+)(["\'”’)\]]*)(\s+|$)')
_INITIAL = re.compile(r"\b[A-Z]\.$")


class Sentence:
    """One sentence, keeping the offset it came from.

    The offset is not decoration: every fact this engine later asserts cites the
    sentence it came from, so a writer can always be shown *why* the system
    believes something.
    """

    __slots__ = ("index", "text", "start", "end")

    def __init__(self, index, text, start, end):
        self.index = index
        self.text = text
        self.start = start
        self.end = end

    def __repr__(self):
        return f"<Sentence {self.index}: {self.text[:40]!r}>"


def _is_real_break(text, period_pos):
    """Would splitting here cut an abbreviation or an initial in half?"""
    before = text[:period_pos]
    last_word = re.split(r"[\s(\[\"']", before)[-1] if before else ""
    if _INITIAL.search(last_word + "."):
        return False
    return last_word.strip().lower().strip(".") not in ABBREVIATIONS


_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")


def split_sentences(text):
    """Split into `Sentence` objects, preserving source offsets.

    A blank line ends a sentence as surely as a full stop does. Without that, a
    scene break (`***`) or a heading gets absorbed into the sentence that
    follows it, and every later stage inherits the mess — an event's text then
    carries a `***` prefix and no longer matches the scene it belongs to.
    """
    text = text.replace("\r\n", "\n")
    sentences = []

    cursor = 0
    for paragraph in _PARAGRAPH_BREAK.split(text):
        offset = text.find(paragraph, cursor) if paragraph else cursor
        if offset == -1:
            offset = cursor
        cursor = offset + len(paragraph)
        if not paragraph.strip():
            continue

        start = 0
        for m in _SENTENCE_END.finditer(paragraph):
            if not _is_real_break(paragraph, m.start(1)):
                continue
            end = m.end(2)
            chunk = paragraph[start:end].strip()
            if chunk:
                sentences.append(Sentence(len(sentences), chunk,
                                          offset + start, offset + end))
            start = m.end()

        tail = paragraph[start:].strip()
        if tail:
            sentences.append(Sentence(len(sentences), tail,
                                      offset + start, offset + len(paragraph)))
    return sentences


def split_clauses(sentence_text):
    """Split a sentence on coordinating conjunctions and semicolons.

    "Aldric died in 1147 and Mara was crowned the same year" is two events, not
    one. Splitting here is what lets each half get its own subject and its own
    time — without it the second event silently inherits the first one's, which
    is exactly the kind of quiet wrongness that makes a timeline untrustworthy.
    """
    parts = re.split(r";|\s+(?:and then|and|but|then|while|whereupon)\s+", sentence_text)
    return [p.strip() for p in parts if p and p.strip()]
