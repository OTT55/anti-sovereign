"""Knowledge graph construction and static SVG rendering. Takes plain entity/relationship
data structures — no database coupling — so any store can feed it.
"""

from xml.sax.saxutils import escape


def build_graph(entities, relationships):
    """entities: [{"name", "type", "doc_ids": [...]}]  relationships: [{"source", "target", "label"}]
    (name, type) is the node key, so the same entity mentioned across documents merges into
    one node. Returns (nodes, edges): nodes is {(name, type): {"name", "type", "doc_ids": set}}.
    """
    nodes = {}
    for e in entities:
        key = (e["name"], e["type"])
        if key not in nodes:
            nodes[key] = {"name": e["name"], "type": e["type"], "doc_ids": set()}
        nodes[key]["doc_ids"].update(e.get("doc_ids", []))

    name_type_by_name = {}
    for name, etype in nodes:
        name_type_by_name.setdefault(name, (name, etype))

    edges = []
    for r in relationships:
        src = name_type_by_name.get(r["source"])
        tgt = name_type_by_name.get(r["target"])
        if src is None or tgt is None:
            continue
        edges.append({"source": src, "target": tgt, "label": r["label"]})

    return nodes, edges


def graph_svg(nodes, edges, width=760, height=520):
    """Render a knowledge graph as inline SVG using a NetworkX spring layout.
    Static (no drag/zoom) by design — a real graph, not a polished one.
    """
    import networkx as nx

    if not nodes:
        return None

    g = nx.Graph()
    for key in nodes:
        g.add_node(key)
    for e in edges:
        g.add_edge(e["source"], e["target"])

    pos = nx.spring_layout(g, seed=42, k=1.6 / max(len(nodes), 1) ** 0.5)
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    pad = 60

    def scale(x, y):
        sx = pad + (x - x_min) / (x_max - x_min or 1) * (width - 2 * pad)
        sy = pad + (y - y_min) / (y_max - y_min or 1) * (height - 2 * pad)
        return sx, sy

    coords = {key: scale(*pos[key]) for key in nodes}

    parts = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" font-family="system-ui,sans-serif">']
    for e in edges:
        if e["source"] not in coords or e["target"] not in coords:
            continue
        x1, y1 = coords[e["source"]]
        x2, y2 = coords[e["target"]]
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#2a222c" stroke-width="1.5"/>')
        parts.append(f'<text x="{mx:.1f}" y="{my:.1f}" fill="#8f8593" font-size="9.5" text-anchor="middle">{escape(e["label"])}</text>')
    for key, (x, y) in coords.items():
        name, etype = key
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="#d44e8f"/>')
        parts.append(f'<text x="{x:.1f}" y="{y - 12:.1f}" fill="#ececf0" font-size="11.5" text-anchor="middle" font-weight="600">{escape(name)}</text>')
        parts.append(f'<text x="{x:.1f}" y="{y + 20:.1f}" fill="#8f8593" font-size="9.5" text-anchor="middle" text-transform="uppercase">{escape(etype)}</text>')
    parts.append("</svg>")
    return "".join(parts)
