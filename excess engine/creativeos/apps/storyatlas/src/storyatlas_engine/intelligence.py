"""Phase 7 — Narrative Intelligence: the coordinator.

The StoryAtlas counterpart to CreativeOS's Intelligence Engine, and built the
same way: it delegates to the engines that own each capability and adds almost
no logic of its own. Comprehension, typing, scenes, relationships, the
timeline, canon and structure already exist; this assembles them into the one
thing a writer actually wants, which is *a report on my draft*.

The ordering rule is the only real judgement here: **errors before absences**.
A continuity break makes the draft wrong, whereas a missing date makes it
incomplete, and a report that mixes the two teaches a writer to skim it.
"""

from . import canon, grouping, presence, structure
from .reading import read


class Report:
    """Everything StoryAtlas understands about a draft."""

    def __init__(self, reading, violations, threads, observations, pacing,
                 eras=None, scene_dates=None):
        self.reading = reading
        self.violations = violations
        self.threads = threads
        self.observations = observations
        self.pacing = pacing
        #: The timeline sliced into periods, each carrying its cast (Phase 8).
        self.eras = eras or []
        #: Where each scene sits in time, and how firmly (Phase 8).
        self.scene_dates = scene_dates or []

    def grid(self, span=10):
        """The character-by-era table: who is alive, present, or missing."""
        return grouping.timeline_grid(self.reading, span=span)

    def worklist(self, limit=None):
        """The ranked, actionable version of this report (Phase 9)."""
        from .worklist import worklist as build
        return build(self, limit=limit)

    @property
    def errors(self):
        return [v for v in self.violations if v.severity == "error"]

    @property
    def warnings(self):
        return [v for v in self.violations if v.severity == "warning"]

    def summary(self):
        r = self.reading
        return {
            "scenes": len(r.scenes),
            "characters": len(r.people()),
            "events": len(r.events),
            "dated_events": len(r.timeline.dated),
            "computed_dates": sum(1 for p in r.timeline.placements
                                  if p.source == "computed"),
            "relationships": len(r.relations),
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "questions": len(r.questions),
            "observations": len(self.observations),
        }

    def render(self):
        r = self.reading
        s = self.summary()
        lines = ["# Draft report", ""]
        lines.append(
            f"{s['scenes']} scenes · {s['characters']} characters · "
            f"{s['events']} events ({s['computed_dates']} dates computed) · "
            f"{s['relationships']} relationships")
        lines.append("")

        if self.errors:
            lines.append("## Continuity errors")
            for v in self.errors:
                lines.append(f"- {v.text}")
                if v.evidence:
                    lines.append(f"    “{v.evidence.strip()[:70]}”")
            lines.append("")

        if self.warnings:
            lines.append("## Possible problems")
            for v in self.warnings:
                lines.append(f"- {v.text}")
            lines.append("")

        # `conflict` and `lifespan` questions are reported above as errors.
        # A writer meeting the same problem twice under two headings stops
        # trusting either one.
        pending = [q for q in r.questions if q.kind not in ("conflict", "lifespan")]
        if pending:
            lines.append("## Needs confirmation")
            for q in pending[:8]:
                lines.append(f"- {q.text}")
            lines.append("")

        if self.eras:
            lines.append("## The cast, era by era")
            for era in self.eras:
                if not era.alive and not era.events:
                    continue
                lines.append(f"- {era.describe()}")
                if era.offstage:
                    lines.append(f"    offstage: {', '.join(era.offstage)}")
            lines.append("")

        if self.observations:
            lines.append("## About the shape of the draft")
            for o in self.observations:
                lines.append(f"- {o.text}")
            lines.append("")

        if self.threads:
            lines.append("## Characters")
            for t in self.threads:
                lines.append(f"- {t.describe()}")

        return "\n".join(lines).strip()


def analyse(text, known_names=None, era_label="Year"):
    """Read a draft and report on it. The single entry point for the app."""
    reading = read(text, known_names=known_names, era_label=era_label)

    # Phase 5's rules and Phase 8's reconciliation produce the same type and are
    # merged rather than reported separately. A writer should not have to learn
    # that "acting before your organisation was founded" and "acting after your
    # own death" come from different modules — they are one kind of problem.
    violations = canon.dedupe(canon.check(reading) + presence.reconcile(reading))

    return Report(
        reading=reading,
        violations=violations,
        threads=structure.threads(reading),
        observations=structure.observations(reading),
        pacing=structure.pacing(reading),
        eras=grouping.eras(reading, era_label=era_label),
        scene_dates=presence.date_scenes(reading),
    )
