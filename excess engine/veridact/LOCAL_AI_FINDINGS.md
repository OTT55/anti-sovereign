# Local AI evaluation — the Veridact engine's verdict

## First, a correction

`companies/veridact/LOCAL_AI_EVALUATION.md` describes testing a function called
`deepen_draft()` against fantasy place names "Ember Hollow" and "Ravenmoor".

**That function does not exist in Veridact.** Searching the whole repository,
`deepen_draft` appears in exactly one place — that document — and in no Veridact
source file. It is Story Atlas's evaluation, copied across.

So Veridact has **never actually been evaluated** for local-model use, despite
having a document that reads as though it was. Anyone treating that file as
evidence about Veridact is reading about a different application.

---

## The verdict: **(c) leave it as it is — there is nothing here for a model to do.**

This is a different answer from the other three engines, and the reason is
structural rather than a matter of quality.

**Veridact has no AI-shaped task.** The other engines have at least one place
where a model could plausibly help — composing an answer, phrasing a fact,
extracting entities from prose. Veridact's entire job is:

```
does this signature verify against this public key?   →  yes / no
```

That is arithmetic over an elliptic curve. It is not a judgement, not an
inference, and not a summarisation. A model cannot do it better, cannot do it
faster, and — most importantly — **must not be allowed near it**, because the
answer's whole value is that it is checkable by anyone with the public key and
comes out the same every time.

An LLM in this path would replace a proof with an opinion.

---

## What that means concretely

| Candidate | Verdict |
|---|---|
| Verifying signatures | **Never.** Cryptographic verification is exact. A probabilistic answer here is worthless — the point is that anyone can recompute it. |
| Deciding VERIFIED / ALTERED / UNVERIFIED | **Never.** These follow deterministically from three checks. Handing that to a model would let it hedge, and hedging is what the three-verdict rule exists to prevent. |
| Detecting whether media is AI-generated | **Never, and not by anyone.** ADR 0001 already ruled this out: pixel-based detection is an arms race detectors lose. Veridact deliberately does not play. |
| Explaining a verdict in plain language | **Possible, marginal.** The reasons are already written as sentences a person can read. A model could rephrase them, and would add a dependency, latency and a way to be wrong for no gain. |

Rather than adopt anything, the boundary was made explicit in the engine: there
is no model call anywhere in `veridact_engine`, and no seam for one.

---

## The rule, extended

Across four engines now, one line predicts every result:

> **A local model's usefulness is inversely proportional to how much reasoning
> the task requires — and it drops to zero when the task is a proof.**

- **CreativeOS** — rephrasing already-verified facts. **Works.**
- **ContextCore** — summarising retrieved passages. *Usable, but miscites.*
- **StoryAtlas** — chaining relative dates. **Fails**, and is beaten outright by
  arithmetic.
- **Veridact** — verifying a signature. **Not applicable.** There is nothing to
  reason about; there is something to *check*.

---

## What was tested

Nothing was installed and no model was run, because there was no task to run one
against. That is the honest report: not "the model performed poorly here" but
"there is no place in this engine where a model could be given a job."

The engine that was built instead is tested against **real ECDSA P-256 keys** —
19 tests including forgery, replay, expiry, tampering and revocation. The
security property under test is that verification needs only the public key, and
a symmetric stand-in could not have demonstrated it.
