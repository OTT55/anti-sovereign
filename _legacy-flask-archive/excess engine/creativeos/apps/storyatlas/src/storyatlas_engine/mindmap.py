"""Phase 11 — the draft as a navigable graph, and as an Obsidian vault.

*"How does something like this work with a mind map? NotebookLM's mind map makes
more sense at this point."*

It does, and the reason is worth naming, because it decides what this module
builds. Obsidian's graph is useful **not** because it draws circles and lines —
that part is nearly decorative — but because every node is a real note you can
open, and every link was put there by something that knew what it meant. A
picture of a graph is a poster. A graph you can walk is a tool.

So this produces two things from the same structure:

* **a graph** — nodes and weighted edges, for anything that draws;
* **a vault** — one markdown note per character, place, organisation and era,
  cross-linked with `[[wikilinks]]`, which opens in Obsidian with no import
  step and no plugin.

The vault is the point. The engine's findings live in the notes beside the
facts, so the contradiction about Aldric is *on Aldric's page*, where the writer
will be when it matters, rather than in a report they have to remember to open.

Every edge is derived, and every edge says what derived it:

| Edge | Comes from | Meaning |
|---|---|---|
| `relation` | stated relationships | the text says so |
| `appears-with` | shared scenes | they are on the page together |
| `located` | events and scene settings | somebody was somewhere |
| `during` | the solved timeline | when a thing sits |

`appears-with` is weighted by how many scenes a pair shares, so the graph's
shape reflects the draft's actual centre of gravity rather than treating a
single passing encounter as equal to a partnership.
"""

import re
from collections import defaultdict

from .comprehend.typing import CHARACTER, LOCATION, ORGANIZATION
from .grouping import circles, co_presence, eras
from .presence import date_scenes, existences, itinerary, occupancy


class Node:
    __slots__ = ("id", "label", "kind", "attributes")

    def __init__(self, id, label, kind, attributes=None):
        self.id = id
        self.label = label
        self.kind = kind
        self.attributes = attributes or {}

    def __repr__(self):
        return f"<Node {self.kind}:{self.label}>"


class Edge:
    __slots__ = ("source", "target", "kind", "weight", "evidence")

    def __init__(self, source, target, kind, weight=1, evidence=""):
        self.source = source
        self.target = target
        self.kind = kind
        self.weight = weight
        self.evidence = evidence

    def __repr__(self):
        return f"<Edge {self.source} -{self.kind}-> {self.target}>"


class Map:
    """Nodes and edges, plus every rendering of them."""

    def __init__(self, nodes, edges):
        self.nodes = nodes
        self.edges = edges

    def of_kind(self, kind):
        return [n for n in self.nodes if n.kind == kind]

    def neighbours(self, node_id):
        out = set()
        for edge in self.edges:
            if edge.source == node_id:
                out.add(edge.target)
            elif edge.target == node_id:
                out.add(edge.source)
        return sorted(out)

    def central(self, limit=5):
        """The most connected nodes, by summed edge weight.

        Degree, not a centrality algorithm. Something a writer can verify by
        counting is worth more here than something they have to take on faith.
        """
        score = defaultdict(int)
        for edge in self.edges:
            score[edge.source] += edge.weight
            score[edge.target] += edge.weight
        ranked = sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))
        by_id = {n.id: n for n in self.nodes}
        return [(by_id[i], s) for i, s in ranked[:limit] if i in by_id]

    def to_dict(self):
        return {
            "nodes": [{"id": n.id, "label": n.label, "kind": n.kind,
                       **n.attributes} for n in self.nodes],
            "edges": [{"source": e.source, "target": e.target, "kind": e.kind,
                       "weight": e.weight} for e in self.edges],
        }

    def to_mermaid(self, kinds=("relation", "appears-with", "located")):
        """A Mermaid `graph` — renders in Obsidian, GitHub and most editors.

        Node shape carries the entity kind, so the picture is readable without a
        legend: characters are rounded, places are stadium-shaped, organisations
        are hexagons.
        """
        shapes = {CHARACTER: ("(", ")"), LOCATION: ("([", "])"),
                  ORGANIZATION: ("{{", "}}"), "era": ("[", "]")}
        wanted = [e for e in self.edges if e.kind in kinds]
        keep = {e.source for e in wanted} | {e.target for e in wanted}

        lines = ["graph TD"]
        for node in self.nodes:
            if node.id not in keep:
                continue
            open_shape, close_shape = shapes.get(node.kind, ("[", "]"))
            lines.append(f'    {node.id}{open_shape}"{node.label}"{close_shape}')
        for edge in wanted:
            arrow = "---" if edge.kind == "appears-with" else "-->"
            label = f"|{edge.kind}|" if edge.kind != "appears-with" else \
                    (f"|{edge.weight}|" if edge.weight > 1 else "")
            lines.append(f"    {edge.source} {arrow}{label} {edge.target}")
        return "\n".join(lines)

    def to_outline(self):
        """A nested markdown outline — the mind map as text.

        Text rather than a picture because an outline can be searched, diffed,
        pasted into anything and read by someone who cannot see the diagram.
        """
        lines = []
        for kind, heading in ((CHARACTER, "Characters"), (LOCATION, "Places"),
                              (ORGANIZATION, "Organisations"), ("era", "Eras")):
            nodes = self.of_kind(kind)
            if not nodes:
                continue
            lines.append(f"- **{heading}**")
            for node in nodes:
                detail = node.attributes.get("summary", "")
                lines.append(f"    - {node.label}{f' — {detail}' if detail else ''}")
                for neighbour in self.neighbours(node.id)[:6]:
                    match = next((n for n in self.nodes if n.id == neighbour), None)
                    if match and match.kind != kind:
                        lines.append(f"        - {match.label}")
        return "\n".join(lines)

    def __repr__(self):
        return f"<Map {len(self.nodes)} nodes, {len(self.edges)} edges>"


def build(reading, report=None):
    """Build the map from a reading, folding in a report's findings if given."""
    lives = existences(reading)
    scene_dates = date_scenes(reading)
    where = occupancy(reading, scene_dates)
    nodes, edges = [], []
    seen = set()

    def add(name, kind, attributes=None):
        node_id = _slug(name)
        if node_id in seen:
            return node_id
        seen.add(node_id)
        nodes.append(Node(node_id, name, kind, attributes))
        return node_id

    for name, verdict in sorted(reading.types.items()):
        if verdict.kind not in (CHARACTER, LOCATION, ORGANIZATION):
            continue
        existence = lives.get(name)
        attributes = {"scenes": sum(1 for s in reading.scenes if name in s.present)}
        if existence and existence.is_bounded:
            attributes["begins"] = existence.begins
            attributes["ends"] = existence.ends
            attributes["summary"] = existence.describe().split(") ", 1)[-1]
        add(name, verdict.kind, attributes)

    for era in eras(reading):
        if not era.alive and not era.events:
            continue
        add(era.label, "era", {"alive": len(era.alive), "events": len(era.events)})

    for relation in reading.relations:
        if _slug(relation.subject) in seen and _slug(relation.target) in seen:
            edges.append(Edge(_slug(relation.subject), _slug(relation.target),
                              "relation", 1, relation.evidence))

    for (first, second), scenes in sorted(co_presence(reading).items()):
        if _slug(first) in seen and _slug(second) in seen:
            edges.append(Edge(_slug(first), _slug(second), "appears-with",
                              len(scenes)))

    for place, years in where.items():
        if _slug(place) not in seen:
            continue
        for year, people in years.items():
            for person in people:
                if _slug(person) in seen:
                    edges.append(Edge(_slug(person), _slug(place), "located", 1,
                                      f"{year}"))

    for era in eras(reading):
        era_id = _slug(era.label)
        if era_id not in seen:
            continue
        for name in era.appears:
            if _slug(name) in seen:
                edges.append(Edge(_slug(name), era_id, "during", 1))

    return Map(nodes, _merge(edges))


def _merge(edges):
    """Collapse duplicate edges, summing weights.

    A pair linked five times by five scenes is one relationship of strength
    five, not five relationships — and drawn the other way the graph becomes
    unreadable exactly where it is most informative.
    """
    grouped = {}
    for edge in edges:
        key = (edge.source, edge.target, edge.kind)
        if key in grouped:
            grouped[key].weight += edge.weight
        else:
            grouped[key] = Edge(edge.source, edge.target, edge.kind,
                                edge.weight, edge.evidence)
    return sorted(grouped.values(), key=lambda e: (e.kind, -e.weight, e.source))


# ---------------------------------------------------------------------------
# The Obsidian vault
# ---------------------------------------------------------------------------

def vault(reading, report=None):
    """The whole draft as linked markdown — `{filename: contents}`.

    Write the dictionary to a folder and open it in Obsidian. Every fact cites
    the sentence it came from, and every finding sits on the page of the thing
    it is about.
    """
    lives = existences(reading)
    scene_dates = {d.scene_index: d for d in date_scenes(reading)}
    findings = defaultdict(list)
    if report is not None:
        for violation in report.violations:
            if violation.subject:
                findings[violation.subject].append(
                    f"**{violation.severity}** — {violation.text}")

    files = {}
    windows = eras(reading)

    for name, verdict in sorted(reading.types.items()):
        if verdict.kind == CHARACTER:
            files[f"{_safe(name)}.md"] = _character_note(
                reading, name, lives.get(name), scene_dates, windows,
                findings.get(name, []))
        elif verdict.kind in (LOCATION, ORGANIZATION):
            files[f"{_safe(name)}.md"] = _place_note(
                reading, name, lives.get(name), verdict.kind,
                findings.get(name, []))

    for era in windows:
        if not era.alive and not era.events:
            continue
        files[f"{_safe(era.label)}.md"] = _era_note(era)

    files["Index.md"] = _index_note(reading, windows, report)
    return files


def _character_note(reading, name, existence, scene_dates, windows, findings):
    lines = [f"# {name}", "", "#character", ""]

    if existence and existence.is_bounded:
        born = existence.begins if existence.begins is not None else "?"
        died = existence.ends if existence.ends is not None else "?"
        lines += [f"**Alive:** {born} – {died}", ""]
        if existence.begins_evidence:
            lines.append(f"> {existence.begins_evidence.strip()}")
        if existence.ends_evidence:
            lines.append(f"> {existence.ends_evidence.strip()}")
        lines.append("")

    if findings:
        lines += ["## Needs attention", ""]
        lines += [f"- {f}" for f in findings]
        lines.append("")

    travels = itinerary(reading, name)
    if travels:
        lines += ["## Where and when", ""]
        lines += [f"- {year} — [[{_safe(place)}|{place}]]" for year, place in travels]
        lines.append("")

    relations = [r for r in reading.relations if name in (r.subject, r.target)]
    if relations:
        lines += ["## Connections", ""]
        for relation in relations:
            other = relation.target if relation.subject == name else relation.subject
            lines.append(f"- {relation.relation} — [[{_safe(other)}|{other}]]")
        lines.append("")

    scenes = [s for s in reading.scenes if name in s.present]
    if scenes:
        lines += ["## Scenes", ""]
        for scene in scenes:
            date = scene_dates.get(scene.index)
            when = f" ({date.year})" if date and date.year is not None else ""
            lines.append(f"- Scene {scene.index + 1}{when} — {scene.title}")
        lines.append("")

    present_in = [e for e in windows if name in e.appears]
    if present_in:
        lines += ["## Eras", ""]
        lines += [f"- [[{_safe(e.label)}|{e.label}]]" for e in present_in]
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _place_note(reading, name, existence, kind, findings):
    lines = [f"# {name}", "", f"#{kind}", ""]
    if existence and existence.is_bounded:
        opens = existence.begins if existence.begins is not None else "?"
        closes = existence.ends if existence.ends is not None else "?"
        lines += [f"**Exists:** {opens} – {closes}", ""]

    if findings:
        lines += ["## Needs attention", ""] + [f"- {f}" for f in findings] + [""]

    years = occupancy(reading).get(name, {})
    if years:
        lines += ["## Who was here", ""]
        for year, people in years.items():
            linked = ", ".join(f"[[{_safe(p)}|{p}]]" for p in people)
            lines.append(f"- {year} — {linked}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _era_note(era):
    lines = [f"# {era.label}", "", "#era", ""]
    if era.born:
        lines.append("**Born:** " + ", ".join(f"[[{_safe(n)}|{n}]]" for n in era.born))
    if era.died:
        lines.append("**Died:** " + ", ".join(f"[[{_safe(n)}|{n}]]" for n in era.died))
    lines.append("")
    if era.appears:
        lines += ["## On the page", ""]
        lines += [f"- [[{_safe(n)}|{n}]]" for n in era.appears]
        lines.append("")
    if era.offstage:
        lines += ["## Alive but offstage", ""]
        lines += [f"- [[{_safe(n)}|{n}]]" for n in era.offstage]
        lines.append("")
    if era.events:
        lines += ["## Events", ""]
        lines += [f"- {p.year} — {p.event.text.strip()[:90]}" for p in era.events]
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _index_note(reading, windows, report):
    lines = ["# Index", ""]
    if report is not None:
        s = report.summary()
        lines += [f"{s['scenes']} scenes · {s['characters']} characters · "
                  f"{s['events']} events · {s['errors']} errors", ""]

    groups = circles(reading, minimum=1)
    real = [c for c in groups if c.size > 1]
    if real:
        lines += ["## Circles", ""]
        for circle in real:
            members = ", ".join(f"[[{_safe(m)}|{m}]]" for m in circle.members)
            lines.append(f"- {members} — {len(circle.scenes)} shared scenes")
        lines.append("")

    lines += ["## Eras", ""]
    lines += [f"- [[{_safe(e.label)}|{e.label}]] — {len(e.alive)} alive, "
              f"{len(e.appears)} on the page" for e in windows]
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def write_vault(reading, directory, report=None):
    """Write the vault to disk. Returns the paths written."""
    import os
    os.makedirs(directory, exist_ok=True)
    written = []
    for filename, contents in vault(reading, report).items():
        path = os.path.join(directory, filename)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(contents)
        written.append(path)
    return written


def _slug(name):
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", str(name)).strip("_")
    return cleaned or "n"


def _safe(name):
    """A filename Obsidian and every filesystem will accept."""
    return re.sub(r'[\\/:*?"<>|]+', "-", str(name)).strip() or "untitled"


__all__ = ["Map", "Node", "Edge", "build", "vault", "write_vault"]
