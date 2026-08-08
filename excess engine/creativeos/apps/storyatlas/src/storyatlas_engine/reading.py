"""Reading a draft: the whole pipeline, and what the engine wants confirmed.

    text -> sentences -> clauses -> mentions -> events -> solved timeline
                                                       -> groupings
                                                       -> questions

The last output is the one that matters most to a writer. The engine is not
allowed to quietly guess: where it cannot tell who died, or when something
happened, or whether "he" meant Aldric, it produces a **Question** rather than
an assertion. Confirmed answers become facts; unanswered ones stay visibly
unknown.

That is a deliberate inversion of how the current app works. Today the writer
types everything in and the software stores it. Here the engine proposes what it
understood and asks about what it did not — so the writer is confirming, not
transcribing.
"""

from collections import defaultdict

from .comprehend import typing as typing_mod
from .comprehend.events import extract_events
from .comprehend.mentions import MentionIndex, discover_names, resolve_pronoun_subject
from .comprehend.relations import extract_relations
from .comprehend.scenes import detect_scenes
from .comprehend.segment import split_clauses, split_sentences
from .comprehend.solver import lifespans, solve
from .comprehend.temporal import extract_time
from .comprehend.typing import CHARACTER, classify

#: Below this, the engine asks instead of asserting.
CONFIRM_BELOW = 0.7

#: How many recent mentions a pronoun may reach back through. Small on purpose:
#: it exists to step over places and organisations standing between "he" and the
#: person meant, not to hunt for an antecedent across a page.
ANTECEDENT_WINDOW = 3


def _resolve_deferred_pronouns(deferred, types):
    """Attach pronoun subjects now that every name has a type.

    The rule is still "the most recent subject", exactly as before — with the
    single change that a personal pronoun may now **reach past** a place, an
    organisation or a named event to get there, because none of those can be a
    "he" or a "she". It does not search further than that, and it never chooses
    between two people; a wrong antecedent attributes a death to the wrong
    character, silently, and then propagates through every date computed after
    it.

    Returns the questions to raise, since every resolution here is a proposal
    for the writer to confirm rather than a fact.
    """
    def is_person(name):
        verdict = types.get(name)
        if verdict is None:
            return True
        return verdict.kind not in (typing_mod.LOCATION, typing_mod.ORGANIZATION,
                                    typing_mod.EVENT)

    questions = []
    for event, clause, candidates in deferred:
        nearest = next((n for n in reversed(candidates) if is_person(n)), None)
        if nearest is None:
            continue
        inferred = resolve_pronoun_subject(clause, [nearest])
        if not inferred:
            continue
        # Carried over from the previous sentence, so it is a proposal to
        # confirm, not a fact.
        event.patient = inferred
        event.confidence = min(event.confidence, 0.6)
        questions.append((event, inferred, clause))
    return questions


class Question:
    """Something the engine needs a human to settle.

    `kind` is one of `who`, `when`, `pronoun`, `conflict`, `lifespan`.
    `options` are the engine's best candidates — a writer picking from three
    names is doing far less work than typing one, which is the point.
    """

    __slots__ = ("kind", "text", "about", "options", "evidence", "sentence_index")

    def __init__(self, kind, text, about=None, options=None, evidence="", sentence_index=None):
        self.kind = kind
        self.text = text
        self.about = about
        self.options = options or []
        self.evidence = evidence
        self.sentence_index = sentence_index

    def __repr__(self):
        return f"<Question {self.kind}: {self.text}>"


class Reading:
    """Everything the engine understood from one draft."""

    def __init__(self, text, sentences, events, timeline, names, questions,
                 types=None, scenes=None, relations=None, non_factual=None):
        self.text = text
        self.sentences = sentences
        self.events = events
        self.timeline = timeline
        self.names = names
        self.questions = questions
        #: `{name: TypeVerdict}` — what kind of thing each name is.
        self.types = types or {}
        #: Scenes, in narrative order (Phase 3).
        self.scenes = scenes or []
        #: Typed relationships, stated and inferred (Phase 4).
        self.relations = relations or []
        #: Events the text mentions but does not assert — denied, hypothetical,
        #: future or asked. Kept out of the timeline, surfaced as questions.
        self.non_factual = non_factual or []

    # -- scenes and relationships -----------------------------------------

    def scenes_with(self, name):
        """Every scene a character appears in."""
        return [s for s in self.scenes if name in s.present]

    def relations_for(self, name):
        return [r for r in self.relations if r.subject == name]

    def stated_relations(self):
        return [r for r in self.relations if not r.inferred]

    def who_is_in_every_scene(self):
        """Characters present throughout — usually the protagonists."""
        if not self.scenes:
            return []
        common = set(self.scenes[0].present)
        for scene in self.scenes[1:]:
            common &= set(scene.present)
        return sorted(common)

    # -- what each name is -------------------------------------------------

    def kind_of(self, name):
        verdict = self.types.get(name)
        return verdict.kind if verdict else typing_mod.UNKNOWN

    def people(self):
        return typing_mod.people(self.types)

    def places(self):
        return typing_mod.places(self.types)

    def organizations(self):
        return typing_mod.organizations(self.types)

    def named_events(self):
        return typing_mod.events(self.types)

    def cast(self):
        """Everything found, grouped by what kind of thing it is."""
        grouped = defaultdict(list)
        for name, verdict in self.types.items():
            grouped[verdict.kind].append(name)
        return dict(grouped)

    # -- the groupings the current app cannot do --------------------------

    def by_kind(self):
        """Events grouped by what kind of thing happened — every death together,
        every birth, every battle."""
        grouped = defaultdict(list)
        for p in self.timeline.placements:
            grouped[p.event.kind].append(p)
        return dict(grouped)

    def by_person(self, people_only=True):
        """Everything that happened to each character, in order.

        `people_only` keeps organisations and wars out of a *per-person* view —
        the whole reason entity typing exists. Pass `False` for every named
        thing regardless of kind.
        """
        grouped = defaultdict(list)
        for p in self.timeline.in_order():
            for name in (p.event.subject, p.event.patient):
                if not name or (name in grouped and p in grouped[name]):
                    continue
                if people_only and self.types and self.kind_of(name) != CHARACTER:
                    continue
                grouped[name].append(p)
        return dict(grouped)

    def by_period(self, span=10):
        """Dated events bucketed into periods, so a long history reads as eras
        rather than a flat list."""
        grouped = defaultdict(list)
        for p in self.timeline.dated:
            grouped[(p.year // span) * span].append(p)
        return dict(sorted(grouped.items()))

    def lifespans(self):
        return lifespans(self.timeline)

    def deaths(self):
        """Who died, and when — the question the current app cannot answer."""
        return [(p.event.subject, p.year) for p in self.timeline.by_kind("death")]

    def summary(self):
        dated = len(self.timeline.dated)
        return {
            "sentences": len(self.sentences),
            "characters": len(self.names),
            "events": len(self.events),
            "dated_events": dated,
            "computed_dates": sum(1 for p in self.timeline.placements if p.source == "computed"),
            "undated_events": len(self.timeline.undated),
            "conflicts": len(self.timeline.conflicts),
            "questions": len(self.questions),
        }


def read(text, known_names=None, era_label="Year"):
    """Comprehend a draft. Deterministic: same text in, same reading out."""
    sentences = split_sentences(text)
    names = list(known_names) if known_names else discover_names(text)
    index = MentionIndex(names)

    events = []
    recent_subjects = []
    deferred_pronouns = []

    for sentence in sentences:
        for clause in split_clauses(sentence.text):
            mentions = index.find(clause)
            time = extract_time(clause, era_label=era_label)
            found = extract_events(clause, sentence.index, mentions, time=time,
                                   sentence_text=sentence.text)

            for event in found:
                if event.subject is None and recent_subjects:
                    # Held over rather than resolved here — see below.
                    deferred_pronouns.append(
                        (event, clause, list(recent_subjects[-ANTECEDENT_WINDOW:])))
                events.append(event)

            subjects = [m[0] for m in mentions]
            if subjects:
                recent_subjects.append(subjects[0])

    # Typed after extraction, so the roles events already worked out can be used
    # as evidence — far stronger than matching surface text.
    # A clause that denies, supposes or asks about an event must not put a fact
    # in the timeline — every date computed from it and every lifespan bounded
    # by it would inherit the error. They are kept separately and surfaced as
    # questions rather than silently dropped.
    factual = [e for e in events if e.is_factual]
    non_factual = [e for e in events if not e.is_factual]

    types = classify(names, text, index, events=factual)

    # Pronouns are resolved *here*, after typing, and not during extraction.
    #
    # The ordering is the fix for a bug that was quietly wrecking timelines.
    # "Dawnhold was founded in 1090. He was crowned at the age of thirty."
    # resolved "he" to Dawnhold, because a castle was simply the nearest thing
    # mentioned. The visible damage was not the odd attribution — it was that
    # the coronation then had no birth year to count thirty from, so it stayed
    # undated, so the *next* sentence's "three years later" anchored to the
    # founding instead, and a death landed forty-two years early. One pronoun
    # re-dated half the draft.
    #
    # Knowing a castle is not a "he" requires types, and good types require
    # events, so resolving during extraction is circular. Deferring breaks the
    # circle: extract first, type on that evidence, then resolve pronouns
    # knowing what everything is.
    pronoun_questions = _resolve_deferred_pronouns(deferred_pronouns, types)

    timeline = solve(factual)
    scenes = detect_scenes(text, sentences, index, events=events, era_label=era_label)
    relations = extract_relations(sentences, index)
    questions = _build_questions(timeline, factual, names, pronoun_questions, types,
                                 non_factual=non_factual)
    return Reading(text, sentences, factual, timeline, names, questions, types,
                   scenes=scenes, relations=relations, non_factual=non_factual)


def _build_questions(timeline, events, names, pronoun_questions, types=None,
                     non_factual=()):
    """Turn everything uncertain into a specific, answerable question.

    Deliberately concrete — "Who died in 'the chancellor fell at Dawnhold'?"
    with candidates, not "some events need review". A vague prompt is one the
    writer ignores.
    """
    questions = []

    # Something the text mentions but does not assert. Worth surfacing — a
    # writer may have meant it, or may want to know the engine saw it and
    # deliberately kept it out of the timeline.
    from .comprehend.factuality import describe as describe_factuality
    for event in non_factual:
        questions.append(Question(
            kind="not-asserted",
            text=f"This {event.kind} is {describe_factuality(event.factuality)} — "
                 "should it be recorded?",
            about=event.subject, evidence=event.text,
            sentence_index=event.sentence_index,
        ))

    # A personal pronoun cannot mean a castle, so a castle must not be offered
    # as an alternative answer. An option the writer would never pick is not a
    # neutral extra — it is one more thing to read past, and it advertises that
    # the engine does not know what it is looking at.
    people = [n for n in names
              if (types or {}).get(n) is None
              or types[n].kind not in (typing_mod.LOCATION,
                                       typing_mod.ORGANIZATION, typing_mod.EVENT)]

    for event, inferred, clause in pronoun_questions:
        alternatives = [n for n in people if n != inferred][:3]
        questions.append(Question(
            kind="pronoun",
            text=f"Does this refer to {inferred}?",
            about=inferred, options=[inferred] + alternatives,
            evidence=clause, sentence_index=event.sentence_index,
        ))

    for p in timeline.placements:
        event = p.event
        if event.subject is None and event.confidence < CONFIRM_BELOW:
            questions.append(Question(
                kind="who",
                text=f"Who does this {event.kind} refer to?",
                options=names[:4], evidence=event.text,
                sentence_index=event.sentence_index,
            ))

    for p in timeline.undated:
        if p.event.subject:
            questions.append(Question(
                kind="when",
                text=f"When did this happen? ({p.event.kind} — {p.event.subject})",
                about=p.event.subject, evidence=p.event.text,
                sentence_index=p.event.sentence_index,
            ))

    for conflict in timeline.conflicts:
        questions.append(Question(
            kind="conflict",
            text=f"This is dated {conflict['year']} but {conflict['problem']}.",
            evidence=conflict["text"],
            sentence_index=conflict["event"].sentence_index,
        ))

    # A name the evidence splits on — or gives nothing at all. Both are asked
    # about. A name with *no* evidence is the easiest one to file wrongly by
    # accident, so silence is not an option there either.
    for name, verdict in (types or {}).items():
        if verdict.confident:
            continue
        options = [k for k, _ in sorted(verdict.scores.items(), key=lambda kv: -kv[1])]
        if not options:
            options = ["character", "location", "organization", "event"]
        questions.append(Question(
            kind="type",
            text=f"What kind of thing is {name}?",
            about=name, options=options[:4], evidence=name,
        ))

    # A character acting outside their own lifespan is the continuity error
    # writers most want caught, and now it is computable.
    spans = lifespans(timeline)
    for p in timeline.dated:
        subject = p.event.subject
        if not subject or p.event.kind in ("birth", "death"):
            continue
        born, died = spans.get(subject, (None, None))
        if died is not None and p.year > died:
            questions.append(Question(
                kind="lifespan",
                text=f"{subject} died in {died}, but this is dated {p.year}.",
                about=subject, evidence=p.event.text,
                sentence_index=p.event.sentence_index,
            ))
        elif born is not None and p.year < born:
            questions.append(Question(
                kind="lifespan",
                text=f"{subject} was born in {born}, but this is dated {p.year}.",
                about=subject, evidence=p.event.text,
                sentence_index=p.event.sentence_index,
            ))

    return questions
