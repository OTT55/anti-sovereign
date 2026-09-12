# StoryAtlas Engine — Architecture Decisions

**Context → Decision → Why → Trade-off → What I rejected.** Written to be
defended later, by someone who does not read code.

---

## 0001 — Time expressions are constraints, not values

**Context.** A draft states a handful of dates and relates everything else to
them. The existing app detects "three years later", finds no number in it, and
stores `year: None` — so the phrase is recognised and then thrown away, which is
why its timeline cannot order anything.

**Decision.** A time expression is stored as a **constraint** on an event, not a
date. "Three years later" becomes `this = previous + 3`. A solver propagates all
of them to a fixpoint and computes the dates nobody wrote down.

**Why.** It converts the problem from language understanding into arithmetic. In
the demo draft, two dates are stated and five are solved for. Nothing about that
needs a model, and being deterministic means the same draft always reads the
same way — which matters for something a writer is trusting with continuity.

**Trade-off.** A wrong anchor propagates. If the engine misreads one date,
everything computed from it is wrong too. Mitigated by marking every date as
`stated` or `computed`, so a writer can see which are inferred and check the
anchors rather than the whole chain.

**What I rejected.** Asking a language model to date events — non-deterministic,
costs money per draft, cannot show its working, and OTT explicitly does not want
API calls. Also rejected: storing only explicit years, which is what the app does
now and is precisely the limitation.

---

## 0002 — Events carry participants and roles, not a category label

**Context.** The app stores an event as the sentence text plus a category
guessed from keywords. That is a label on a string.

**Decision.** An event is `(kind, agent, patient, place, time)`. A death knows
*whose* death it is.

**Why.** Everything downstream depends on it. "Who died?" is unanswerable
without it; so is grouping by person, deriving a lifespan, and every continuity
check. One structural change unlocks all of them.

**Trade-off.** Roles are assigned by English word order rather than a parser —
agent before the verb, patient after, swapped for passives. That is wrong on
genuinely tangled sentences.

**What I rejected.** A full dependency parser (spaCy) — a heavy dependency, and
the accuracy gain does not change the answer on ordinary narrative prose. Also
rejected: silently accepting whatever word order gives, which is why the next
decision exists.

---

## 0003 — Uncertainty becomes a question, never a guess

**Context.** Word-order role assignment and pronoun resolution are both
heuristics. They will sometimes be wrong.

**Decision.** Every event carries a confidence. Below 0.7 it is not asserted —
it becomes a **Question** citing the sentence that prompted it, with candidate
answers where the engine has them. Only confirmed readings reach the graph.

**Why.** A wrong antecedent silently attributes a death to the wrong character,
and a writer may never notice. Being visibly unsure is far cheaper than being
confidently wrong about continuity, which is the one thing this product is for.
It also inverts the work: the writer confirms instead of transcribing.

**Trade-off.** A long draft produces a lot of questions, and an engine that asks
too much is as unusable as one that guesses. Tuning that threshold needs real
drafts.

**What I rejected.** Asserting the best guess and letting the writer correct it
later — corrections only happen if the error is noticed, and quiet errors in a
continuity system are the expensive kind.

---

## 0004 — Pronouns resolve one sentence back, and only when unambiguous

**Context.** "He was crowned at the age of thirty" carries the subject from the
previous sentence. Full coreference resolution is a research problem.

**Decision.** Look back exactly one sentence, and only resolve when exactly one
candidate fits. Otherwise decline, drop the event's confidence, and ask.

**Why.** Most narrative pronouns do refer to the immediately preceding subject,
so this catches the common case cheaply. Reaching further multiplies the chance
of a confident wrong answer, and per 0003 that is the failure mode to avoid.

**Trade-off.** Misses long-range references, so a passage written in a flowing
style produces more questions than it strictly needs to.

**What I rejected.** A coreference model (heavy, non-deterministic), and
nearest-name-wins (frequently wrong when two characters are in a scene, which is
most scenes).

---

## 0005 — Aliases never include connectives

**Context.** A bug found while testing, worth recording because it shows how
quietly this class of error corrupts everything.

`aliases_for("Order of the Broken Crown")` generated `"of"` as a short form.
`"of"` then matched inside "the age **of** thirty", so that clause's subject
resolved to the *organisation*. The pronoun never resolved to Aldric, his
accession never got a date, and every date computed from it was wrong. One bad
alias silently broke the entire timeline.

**Decision.** Connectives (`of`, `the`, `de`, `van`, …) can appear *inside* a
name but never become an alias on their own. Name discovery also keeps
capitalised runs joined across connectives, so the name stays whole.

**Why.** Errors in the mention layer do not stay in the mention layer — they
propagate into roles, then dates, then contradictions. Both fixes are pinned by
regression tests naming the original failure.

**Trade-off.** A name genuinely referred to by a connective cannot be matched.
No real example exists.

**What I rejected.** Filtering at match time instead of alias time — that leaves
the bad alias in the index for something else to trip over later.

---

## 0006 — The engine holds the narrative half, CreativeOS holds the universal half

**Context.** Both layers could plausibly own lifespans and contradiction
detection.

**Decision.** StoryAtlas computes the lifespan — knowing a death bounds a life
is narrative knowledge. CreativeOS stores it as a valid-time window and checks
facts against it, without knowing what a character is.

**Why.** It is Constitution v2.0's rule applied to a real case: *"StoryAtlas
understands kingdoms, CreativeOS understands entities."* The check "a fact
outside its subject's valid window contradicts it" is universal — a licence
outside its term is the same shape — so it belongs to the platform and every
other application gets it free.

**Trade-off.** Two hops to answer one question, and a bug can live on either
side of the seam.

**What I rejected.** Doing continuity checks inside StoryAtlas, which would
duplicate what CreativeOS already does and mean RightsForge has to build it
again. Also rejected: putting narrative vocabulary into CreativeOS, which is the
boundary violation v2.0 exists to prevent.
