"""Finding scenes: where they start, who is in them, where and when they happen.

Phase 3. The Story Atlas app has a scene database the writer fills in by hand.
Everything needed to fill it is already in the prose.

A scene break is signalled three ways, in descending reliability:

* an **explicit marker** — `***`, `---`, `CHAPTER TWO`, `INT. BRIDGE — NIGHT`
* a **blank line** between blocks of prose
* a **shift** in setting or time with no marker at all

The third is the interesting one and the easiest to get wrong. A location
changing mid-paragraph is usually a character walking, not a cut; a location
changing *at a paragraph boundary, alongside a time jump*, usually is a cut.
Requiring both signals keeps false splits low, and a scene split wrongly is
worse than two scenes left joined — a writer notices a missing break far less
than a scene chopped in half.
"""

import re

_MARKER = re.compile(
    r"^\s*(?:\*\s*\*\s*\*|-{3,}|#{1,6}\s|={3,}|~{3,}"
    r"|(?:CHAPTER|PART|ACT|SCENE|BOOK)\b.*"
    r"|(?:INT|EXT)\.\s.*)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_SLUGLINE = re.compile(r"^\s*(?:INT|EXT)\.\s*(?P<where>[^—\-–]+)(?:[—\-–]\s*(?P<when>.+))?$",
                       re.IGNORECASE)


class Scene:
    """One continuous unit of story."""

    __slots__ = ("index", "text", "sentence_range", "present", "place",
                 "time", "marker", "events")

    def __init__(self, index, text, sentence_range, present=None, place=None,
                 time=None, marker=None, events=None):
        self.index = index
        self.text = text
        self.sentence_range = sentence_range
        self.present = present or []
        self.place = place
        self.time = time
        self.marker = marker
        self.events = events or []

    @property
    def title(self):
        """A usable heading: the marker if there was one, else the opening line."""
        if self.marker:
            return self.marker.strip()
        first = re.split(r"(?<=[.!?])\s", self.text.strip())[0]
        return first[:70] + ("…" if len(first) > 70 else "")

    def describe(self):
        where = f" at {self.place}" if self.place else ""
        who = f" — {', '.join(self.present)}" if self.present else ""
        return f"Scene {self.index + 1}: {self.title}{where}{who}"

    def __repr__(self):
        return f"<Scene {self.index}: {self.title[:30]!r}>"


def _blocks(text):
    """Split into blocks on explicit markers and blank lines, keeping markers.

    A marker on its own line ("CHAPTER ONE", "***") is a *heading for what
    follows*, not a scene in itself, so it is carried forward and attached to
    the next block of prose. Treating it as its own scene produces a phantom
    empty scene before every real one.
    """
    out = []
    pending = None   # a marker waiting for the prose it introduces

    for chunk in re.split(r"\n\s*\n", text):
        chunk = chunk.strip()
        if not chunk:
            continue
        current = []
        for line in chunk.split("\n"):
            if _MARKER.match(line):
                if current:
                    out.append((pending, "\n".join(current).strip()))
                    current, pending = [], None
                # A later marker supersedes an unused earlier one.
                pending = line.strip()
            else:
                current.append(line)
        if current:
            out.append((pending, "\n".join(current).strip()))
            pending = None

    if pending:   # a trailing marker with nothing after it
        out.append((pending, ""))
    return [(m, t) for m, t in out if t or m]


def detect_scenes(text, sentences, index, events=None, era_label="Year"):
    """Split a draft into scenes and populate each with who, where and when.

    `index` is a `MentionIndex`; `events` are the extracted events, used to
    attach each event to the scene it occurred in.
    """
    from .temporal import extract_time

    scenes = []
    cursor = 0
    for marker, block in _blocks(text):
        if not block and not marker:
            continue

        start_sentence = cursor
        block_sentences = [s for s in sentences
                           if s.text.strip() and s.text.strip()[:40] in block]
        cursor += max(len(block_sentences), 1)

        present = []
        seen = set()
        for name, _s, _e, _k in index.find(block):
            if name not in seen:
                seen.add(name)
                present.append(name)

        place = None
        when = extract_time(block, era_label=era_label)
        if marker:
            slug = _SLUGLINE.match(marker)
            if slug:
                place = slug.group("where").strip().title()

        scenes.append(Scene(
            index=len(scenes), text=block, marker=marker,
            sentence_range=(start_sentence, cursor),
            present=present, place=place, time=when,
        ))

    if events:
        _attach_events(scenes, events, sentences)
    _infer_places(scenes)
    return scenes


def _attach_events(scenes, events, sentences):
    """Put each event in the scene whose text contains its clause."""
    for event in events:
        for scene in scenes:
            if event.text.strip()[:50] in scene.text:
                scene.events.append(event)
                break


def _infer_places(scenes):
    """Fill in a scene's place from the events it contains, then carry it
    forward.

    Prose states a location once and then assumes it for several scenes, so an
    unstated place is usually the previous one rather than nowhere. Carrying it
    forward is a guess, but a well-founded one — and it stops only when the text
    names somewhere new.
    """
    last = None
    for scene in scenes:
        if scene.place is None:
            for event in scene.events:
                if event.place:
                    scene.place = event.place
                    break
        if scene.place is None:
            scene.place = last
        else:
            last = scene.place
