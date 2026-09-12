# Local AI evaluation — the StoryAtlas engine's verdict

Answering the four questions `LOCAL_AI_EVALUATION.md` requires of anyone picking
it up, tested against **this engine's own task** rather than the generic finding.

Machine: Ollama 0.32.5 running `llama3.2:3b`, spaCy 3.8.13 + `en_core_web_sm`,
`fastcoref` installed. All tested live, not assumed.

---

## The verdict, up front

**(a) No API key is needed. (c) Leave the reasoning path as it is.** The local
LLM is *worse* than the deterministic solver at the one job it was a candidate
for, and non-deterministic on top of that.

**But one local-NLP finding was genuinely worth adopting and is now in the
engine** — see part 2.

**Companion evaluations:** `contextcore/LOCAL_AI_FINDINGS.md` (verdict: **(a)**
API key still needed — its conflict detector returned `false` on an explicit
contradiction) and `creativeos/LOCAL_AI_FINDINGS.md` (verdict: **(b)** local
runtime genuinely sufficient, for phrasing only). One rule explains all three:
**a local model's usefulness is inversely proportional to how much reasoning the
task requires.**

---

## Update (Phase 11) — "is this thing running with Ollama?"

Asked directly, so answered directly.

**Ollama is installed and running on this machine.** `/api/tags` responds with
`llama3.2:3b` locally and `gpt-oss:120b` via the cloud endpoint.

**The engine calls it nowhere.** Not in comprehension, not in the solver, not in
the Phase 8 reconciliation, not in the worklist, not in revision. The verdict
below is unchanged, and Phases 8–11 strengthened rather than weakened it: the
new work is interval arithmetic and set operations, which is the *least*
model-shaped code in the engine.

One seam now exists, and it is off by default:

| | |
|---|---|
| **Where** | `polish.py` — rephrasing a sentence whose facts are already settled |
| **Default** | disabled; `smooth()` returns the original and says "disabled" |
| **Fence** | output rejected unless every name and number survives; on any change, addition or loss the original is returned with the reason recorded |
| **Failure** | unreachable, slow or empty all return the original. No path alters a fact; no path raises |

The fence is what makes the seam safe to exist. The model cannot introduce a
fact here — it can only fail to improve a sentence.

`polish.report()` states the live situation in one line, including when nothing
is running.

---

## Part 1 — Ollama, tested on the engine's own hard case

The task: resolve dates that are stated only in relation to each other. Same
input, three runs, `temperature: 0` — the model's most favourable setting.

Input:

```
Aldric Vane was born in the year 1102.
He was crowned at the age of thirty.
Three years later, the Meridian War began.
```

| | birth | accession | war |
|---|---|---|---|
| **This engine** | 1102 *stated* | **1132** *computed* | **1135** *computed* |
| Ollama run 1 | 1102 | `null` | **1105** ❌ |
| Ollama run 2 | 1102 | `null` | `null` |
| Ollama run 3 | 1102 | `null` | `null` |

Three findings, all against it:

1. **It never did the arithmetic.** `1102 + 30 = 1132` — the accession year came
   back `null` on every run. The whole value of this task is chaining relative
   references, and it chained none.
2. **It was confidently wrong once.** Run 1 returned 1105 for the war, having
   added three to the *birth* year instead of the accession year — anchored to
   the wrong event and stated the result with no hedge.
3. **It was not deterministic at temperature 0.** Run 1 differs from runs 2 and
   3 on identical input. For a continuity checker, an answer that changes
   between runs is not an answer.

Speed: 6–15s per call against microseconds for the solver.

This matches the original evaluation's finding ("confidently fabricates on
exactly the reason-out-relative-dates job") and extends it: on this engine's
task the model does not merely fabricate, it **under-answers** — `null` where a
correct answer was computable from information present in the passage.

**Conclusion: not wired in.** Not as a replacement, not as a fallback. It would
make a deterministic, correct, instant result probabilistic, slower and
sometimes wrong.

**Where it *could* earn a place**, and where the seam already exists: CreativeOS's
AI Orchestrator routes providers by capability and is fully functional with none
registered. An Ollama provider could be registered there for a *phrasing* task —
turning an assembled, already-correct answer into prose. It must never be given
a job whose correctness matters, and nothing in either engine depends on it.

---

## Part 2 — What *was* worth adopting: spaCy lemmas

The original evaluation's strongest verified finding was that a dependency
parse catches event verbs **by lemma**, where a regex list only catches the
inflections someone thought to type. Tested against this engine's own trigger
list:

| Sentence | Regex tier | Lemma tier |
|---|---|---|
| "Tobin **founded** the Order" | ✅ | ✅ |
| "Tobin **was founding** the Order" | ❌ | ✅ |
| "Tobin **founds** the Order" | ❌ | ✅ |
| "Mara **was betraying** Aldric" | ❌ | ✅ |
| "Kell **journeys** to Dawnhold" | ❌ | ✅ |

One in five, against five in five. Now in `comprehend/lemmas.py` as a **second
tier**, and three things about how it was fitted matter:

- **Additive, not a replacement.** The regex tier catches multi-word patterns
  ("took the throne") a single-token lemma lookup cannot see. Neither is
  strictly better, so the lemma tier is consulted only when the regex tier
  finds nothing.
- **The parser is switched off.** Lemmas come from the tagger; passive voice is
  detected from a neighbouring "be" auxiliary instead of a dependency tree.
  Same results, 25% faster. Verified that enabling the parser changes no
  outcome here.
- **It degrades honestly.** Without spaCy it returns `None` — meaningfully
  different from `[]` — and the engine carries on with the regex tier alone.

**A real limit, found by testing rather than assumed:** spaCy's small model tags
"perishes" as a NOUN with lemma "perishe", so the lemma tier cannot see it. The
regex tier covers it. That is the clearest argument for keeping both.

**Two bugs this work exposed**, both now fixed and pinned by tests:

- Trigger order was load-bearing and wrong in three places. A passive form
  contains its own active form, so "was betrayed" was matching the active
  `betrayed` first and **reversing who betrayed whom**. Passive variants now
  precede their active counterparts.
- Refactoring for the second tier briefly dropped first-match-wins, which made
  one clause emit two contradictory events.

Cost: the suite went from 0.4s to 15s, since spaCy parses every clause the
regex missed. Bounded by only parsing clauses that actually name someone — an
event with no participants is of no use here anyway.

---

## Part 3 — Not adopted, with reasons

| Tool | Decision |
|---|---|
| **fastcoref** | Installed and working, but **not wired in.** It resolves pronouns, which this engine already handles conservatively one sentence back, and asking the writer to confirm is *better* than resolving silently — a wrong antecedent attributes a death to the wrong character. Worth revisiting only if confirmation load becomes a complaint. |
| **REBEL** | The original evaluation tested it and found it fabricated a date triple. Not retried. |
| **dateparser** | Rejected there for inverting direction on "a decade after". This engine independently built the deterministic offset parser that replaced it — convergent, and it resolves every case that tool failed. |
| **llama.cpp / vLLM / LocalAI / LM Studio / Jan** | Unchanged from the original evaluation: not viable on this hardware, or needing an install this session was not authorised to perform. |
