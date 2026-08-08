# Local AI evaluation — the CreativeOS engine's verdict

Answering the four questions `LOCAL_AI_EVALUATION.md` requires, tested against
**CreativeOS's own AI-relevant surface**: the AI Orchestrator.

Tested live: Ollama 0.32.5, `llama3.2:3b`, `temperature: 0`.

---

## Verdict: **(b) a local runtime is genuinely sufficient here — for one job.**

This is the only one of the three engines where the answer is yes, and the
reason is structural rather than lucky.

CreativeOS never asks a model to *establish* anything. The Context Engine has
already retrieved the facts, budgeted them, attached their provenance, and
flagged any contradictions. What reaches the model is correct by construction.
Its only job is to turn that into a sentence — and rephrasing is the one thing
a 3B model does reliably.

---

## What was tested

Registering Ollama as a provider required **no change to the engine**. The
Orchestrator routes by capability and a provider is any callable, so this is
the whole integration:

```python
def ollama_provider(prompt, **opts):
    ...  # one HTTP POST to localhost:11434
ai.register("ollama", ollama_provider, capabilities=("generate",))
```

Results:

| Condition | Mode | Outcome |
|---|---|---|
| No provider registered | `extractive` | Answers from the graph — the default path |
| Ollama registered | `generative` via `ollama`, 6s | Correct, grounded, well-phrased |
| Provider raises | `extractive` | Still answers, with the reason recorded |

The generated answer, from graph facts alone:

> "We know that Aldric Vane is a character and a navigator, and he was alive
> from 1102 to 1147."

Accurate, grounded, nothing invented. Every fact in that sentence came from the
assembled context, and the model added only grammar.

The failure path is equally important and behaved correctly: with a provider
that throws, the answer came back `extractive`, still contained the right
content, and carried a note naming the failure. **The mode is never
misreported** — it does not claim a call happened when it did not.

---

## Why this one works when the others do not

Across the three engines, one rule explains every result:

> **A local model's usefulness is inversely proportional to how much reasoning
> the task requires.**

- **CreativeOS** hands it verified facts and asks for a sentence → works.
- **ContextCore** asks it to judge whether passages conflict → it returned
  `false` on an explicit contradiction while describing that contradiction in
  its own explanation. See `contextcore/LOCAL_AI_FINDINGS.md`.
- **StoryAtlas** asks it to chain relative dates → it never computed
  `1102 + 30`, was confidently wrong once, and was non-deterministic at
  temperature 0. See `storyatlas/LOCAL_AI_FINDINGS.md`.

The architecture already encodes this rule. Constitution v2.0 says *"AI is
infrastructure, not product"*, and the Orchestrator was deliberately built last,
behind an interface, fully functional with nothing registered. That design is
what makes a local model safe to add here: **nothing depends on it.** Remove the
provider and every answer still comes back, from the graph, correct.

---

## What was changed

**Nothing.** No provider is registered by default and no dependency was added.
The Orchestrator ships exactly as before — fully functional with no model — and
the tests still register plain callables rather than any real runtime.

Wiring Ollama in permanently is a one-function change whenever it is wanted. It
is left out because it should be a deliberate choice, not a default: it turns a
deterministic answer into a probabilistic one, and buys only nicer phrasing.

**The boundary to hold:** register a local model for `generate` (phrasing) only.
Never give it a capability whose output something else trusts — no extraction,
no judgement, no arithmetic. Those belong to the deterministic engines, which
are faster, correct, and the same every time.
