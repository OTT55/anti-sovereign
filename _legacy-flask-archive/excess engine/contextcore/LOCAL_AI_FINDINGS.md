# Local AI evaluation — the ContextCore engine's verdict

Answering the four questions `LOCAL_AI_EVALUATION.md` requires, tested against
**ContextCore's own three AI-gated paths** rather than the generic finding.

Tested live: Ollama 0.32.5, `llama3.2:3b`, `temperature: 0`, two runs each.

---

## Verdict: **(a) an API key is still needed.**

ContextCore has three Claude-gated paths and the local model behaves completely
differently on each. One is usable, one is broken, and one is **dangerous**.

| Path | Local model | Verdict |
|---|---|---|
| `generate_answer` — compose an answer from retrieved passages | Right answer, wrong citation | Usable with review |
| `detect_conflict` — do these passages disagree? | **Says `false` on a real conflict** | **Do not use** |
| `extract_entities_relationships` — structured JSON | Wrong schema, 0 entities parsed | Do not use |

---

## Path 1 — Answer composition: usable, but it misattributes evidence

Corpus states plainly: *"The Accord did not cover military vessels."*
Question: *"Does the Accord cover military vessels?"*

Retrieval (deterministic) found the correct passage. Ollama then answered:

> "No, according to [Chunk 1], the Meridian Accord does not cover military
> vessels. It specifically states that *'It guaranteed free passage through the
> Sundered Strait for all signatory fleets'*…"

**The conclusion is right and identical across runs.** But the quote it cites as
proof is the wrong sentence — the actual evidence is the one after it. For a
product whose entire value proposition is *citations you can check*, a right
answer attached to the wrong source is a specific and serious failure mode: it
survives a glance and fails an audit.

Usable only where a human reads the citation. Not unattended.

---

## Path 2 — Conflict detection: the dangerous one

Two passages, an explicit contradiction (ratified **1148** vs **1151**):

> `{"conflict": false, "explanation": "The two passages agree on the general
> timeline but differ by one year regarding when ratification was completed."}`

Three separate failures in one response:

1. **It answered `false`** on a plain, explicit contradiction.
2. **Its own explanation describes the contradiction it just denied.** The
   structured field and the prose field disagree with each other — and only the
   structured field is what code reads.
3. **"differ by one year"** — 1148 to 1151 is three.

Then the control case: passages that genuinely *agree* also returned `false`.
So the function returns `false` for everything. It has **no discriminative
power at all** — it is a constant function wearing the shape of a judgement.

This is worse than having no conflict detection. An absent checker leaves you
uncertain; one that always says "no conflict" gives false assurance, and
ContextCore's whole honesty convention is that the system says when it does not
know. Consistent across runs, so temperature will not save it.

---

## Path 3 — Structured extraction: wrong schema, silently

Asked for `{"entities":[{"name":…,"type":…}]}`. Returned:

```json
{"entities": ["Chancellor Aldric Vane", "Coastal Assembly", …]}
```

Flat strings, no types. Fed through ContextCore's **real** parser:

```
entities recovered: 0 of 2  ->  []
```

It does not crash. It returns empty, which reads downstream as *"this document
had no entities"* — a wrong answer indistinguishable from a true one. The
relationships were also wrong in substance: *"Aldric Vane — signed → Coastal
Assembly"*, when the text says he is *of* that assembly and signed the Accord.

The original evaluation found Ollama good at entity **re-typing** (fixing a type
on a list it was handed). That is not the same task as extraction from prose,
and the difference matters.

---

## The pattern across all three engines

Testing the same model against StoryAtlas, ContextCore and CreativeOS gives one
consistent rule:

> **Its usefulness is inversely proportional to how much reasoning the task
> requires.**

| Task | Reasoning needed | Result |
|---|---|---|
| Rephrase facts already assembled and verified (CreativeOS) | None | **Good** |
| Summarise retrieved passages (ContextCore path 1) | Little | Usable, cites wrong |
| Judge whether two passages conflict (path 2) | Real judgement | **Fails, silently** |
| Emit a schema (path 3) | Instruction-following | Fails |
| Chain relative dates (StoryAtlas) | Arithmetic + inference | Fails |

The safe rule: a local model may **phrase** something the deterministic engine
already established. It may not **decide** anything.

---

## What was changed here

**Nothing.** No local runtime is wired into ContextCore, and the Claude path is
untouched, per the evaluation's instruction not to override an existing
integration.

The extractive fallback already covers the no-key case honestly, and on path 1
it is *more* trustworthy than the local model, because it quotes the retrieved
passages verbatim instead of paraphrasing them onto the wrong citation.
