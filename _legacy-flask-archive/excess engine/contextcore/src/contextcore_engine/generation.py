"""Generative layer: Claude-composed answers, entity/relationship extraction, conflict
detection. Every function degrades gracefully with no API key or no credit — it returns
an honest note explaining what didn't run, never a fabricated result standing in for one.
"""

import json
import os
import re

DEFAULT_MODEL = "claude-sonnet-5"


def extractive_answer(passages):
    if not passages:
        return "No relevant passage was found in this document."
    return "Based on the most relevant passages:\n\n" + "\n\n".join(
        f"[Chunk {i + 1}] {text}" for i, text in passages
    )


def generate_answer(question, passages, api_key=None, model=DEFAULT_MODEL):
    """Return (answer_text, mode, note). mode is 'generative' or 'extractive'."""
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return extractive_answer(passages), "extractive", \
            "No ANTHROPIC_API_KEY set — showing an extractive answer from the retrieved passages."
    try:
        import anthropic
    except ImportError:
        return extractive_answer(passages), "extractive", \
            "The `anthropic` package is not installed — showing an extractive answer. `pip install anthropic` to enable generation."

    context = "\n\n".join(f"[Chunk {i + 1}] {text}" for i, text in passages)
    prompt = (
        "Answer the question using ONLY the context below. Cite the chunk numbers "
        "you used in square brackets, e.g. [Chunk 2]. If the context does not "
        f"contain the answer, say so.\n\nContext:\n{context}\n\nQuestion: {question}"
    )
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(model=model, max_tokens=600, messages=[{"role": "user", "content": prompt}])
        return msg.content[0].text, "generative", None
    except Exception as e:  # billing, network, auth — surface honestly, keep working
        return extractive_answer(passages), "extractive", \
            f"Claude call failed ({type(e).__name__}: {e}). Showing an extractive answer instead."


CONFLICT_PROMPT = """Below are passages retrieved from different documents in response to
the same question. Determine whether any of them meaningfully disagree with each other —
not just cover different aspects of the topic, but actually contradict one another.
Respond with ONLY valid JSON (no markdown fences, no commentary), in exactly this shape:

{{"conflict": true|false, "explanation": "short human-readable explanation, empty string if no conflict"}}

Question: {question}

Passages:
{passages}"""


def detect_conflict(question, passages_with_source, api_key=None, model=DEFAULT_MODEL):
    """passages_with_source: [(text, source_label), ...]. Returns (result, note).
    result is None when the check didn't run (fewer than 2 distinct sources, no
    API key/credit, or a call failure) — None means "unknown," never "no conflict."
    """
    sources = {src for _, src in passages_with_source}
    if len(sources) < 2:
        return None, None
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None, "Conflict check skipped — no ANTHROPIC_API_KEY set."
    try:
        import anthropic
    except ImportError:
        return None, "Conflict check skipped — the `anthropic` package is not installed."

    passages_text = "\n\n".join(f"[{src}] {text}" for text, src in passages_with_source)
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model, max_tokens=300,
            messages=[{"role": "user", "content": CONFLICT_PROMPT.format(question=question, passages=passages_text)}],
        )
        raw = re.sub(r"^```(json)?|```$", "", msg.content[0].text.strip(), flags=re.MULTILINE).strip()
        data = json.loads(raw)
        return {"conflict": bool(data.get("conflict")), "explanation": (data.get("explanation") or "").strip()}, None
    except Exception as e:  # billing, network, auth, malformed JSON — surface honestly
        return None, f"Conflict check failed ({type(e).__name__}: {e})."


EXTRACTION_PROMPT = """Extract the real entities and relationships between them from the
text below. Respond with ONLY valid JSON (no markdown fences, no commentary), in exactly
this shape:

{{"entities": [{{"name": "...", "type": "person|organization|product|place|date|concept"}}],
  "relationships": [{{"source": "...", "target": "...", "label": "short verb phrase"}}]}}

Rules:
- Only extract entities that are actually named or clearly identified in the text.
- Every "source" and "target" in relationships must exactly match a "name" in entities.
- If the text has no clear entities, return {{"entities": [], "relationships": []}}.

Text:
{text}"""


def extract_entities_relationships(text, api_key=None, model=DEFAULT_MODEL):
    """Best-effort entity/relationship extraction for one document.

    Returns (entities, relationships, note). entities/relationships are lists of dicts
    ({"name", "type"} / {"source", "target", "label"}) — persistence is the caller's job.
    note is None on success, or an honest explanation of why extraction didn't run/failed.
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return [], [], "No ANTHROPIC_API_KEY set — entity extraction skipped for this document."
    try:
        import anthropic
    except ImportError:
        return [], [], "The `anthropic` package is not installed — entity extraction skipped."

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model, max_tokens=1500,
            messages=[{"role": "user", "content": EXTRACTION_PROMPT.format(text=text[:6000])}],
        )
        raw = re.sub(r"^```(json)?|```$", "", msg.content[0].text.strip(), flags=re.MULTILINE).strip()
        data = json.loads(raw)
    except Exception as e:  # billing, network, auth, malformed JSON — surface honestly
        return [], [], f"Entity extraction failed ({type(e).__name__}: {e})."

    seen = set()
    entities = []
    for e in data.get("entities", []):
        name = (e.get("name") or "").strip()
        etype = (e.get("type") or "concept").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        entities.append({"name": name, "type": etype})

    relationships = []
    for r in data.get("relationships", []):
        src, tgt = (r.get("source") or "").strip(), (r.get("target") or "").strip()
        label = (r.get("label") or "related to").strip()
        if src not in seen or tgt not in seen or src == tgt:
            continue
        relationships.append({"source": src, "target": tgt, "label": label})

    return entities, relationships, None
