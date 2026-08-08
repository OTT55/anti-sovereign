"""The AI Orchestrator — *"AI is infrastructure. Not product."*

Kept for last on purpose. Every other engine answers its questions
deterministically, and that is the right default: a continuity system whose
answers change between runs is not trustworthy. This engine exists so that
*when* a model is genuinely wanted, there is one place it plugs in — behind an
interface, with the context already assembled and the fallback already written.

Three things it does:

* **Routes** a task to a provider, by declared capability rather than by name,
  so swapping providers is configuration.
* **Builds prompts** from the Context Engine's output, so a model sees the same
  budgeted, provenance-carrying context everything else does.
* **Falls back honestly.** With no provider registered it returns the assembled
  context itself, clearly labelled as `extractive`, and says why. It never
  fabricates and never pretends a call happened.

The important property: **with no provider configured this is fully functional.**
It answers from the graph. A model, if ever added, improves the phrasing — it is
not load-bearing.
"""

from ..context import ContextEngine


class Provider:
    """A registered model backend.

    `call(prompt, **options) -> str`. Anything satisfying that works; the
    orchestrator never imports an SDK, so this module has no dependencies and
    no opinion about who serves the request.
    """

    __slots__ = ("name", "call", "capabilities", "priority")

    def __init__(self, name, call, capabilities=(), priority=0):
        self.name = name
        self.call = call
        self.capabilities = set(capabilities) or {"generate"}
        self.priority = priority

    def can(self, capability):
        return capability in self.capabilities

    def __repr__(self):
        return f"<Provider {self.name} {sorted(self.capabilities)}>"


class Answer:
    """A response, and an honest account of how it was produced."""

    __slots__ = ("text", "mode", "note", "context", "provider", "prompt")

    def __init__(self, text, mode, note=None, context=None, provider=None, prompt=None):
        self.text = text
        self.mode = mode          # "generative" | "extractive"
        self.note = note
        self.context = context
        self.provider = provider
        self.prompt = prompt

    @property
    def is_generative(self):
        return self.mode == "generative"

    @property
    def cited_entities(self):
        return self.context.entities if self.context else []

    def summary(self):
        return {
            "mode": self.mode,
            "provider": self.provider,
            "note": self.note,
            "entities": len(self.cited_entities),
            "contradictions": len(self.context.contradictions()) if self.context else 0,
        }

    def __repr__(self):
        return f"<Answer {self.mode} via {self.provider or 'graph'}>"


PROMPT_TEMPLATE = """Answer the question using ONLY the context below. Every claim
must be traceable to it. If the context does not contain the answer, say so
plainly rather than inferring.

{conflict_warning}Context:
{context}

Question: {question}"""

CONFLICT_WARNING = (
    "IMPORTANT: the context contains contradictory facts, listed as CONFLICT. "
    "Do not silently pick one — say that the sources disagree.\n\n"
)


class AIOrchestrator:
    def __init__(self, graph, context=None):
        self.graph = graph
        self.context = context or ContextEngine(graph)
        self.providers = []

    # -- providers ---------------------------------------------------------

    def register(self, name, call, capabilities=("generate",), priority=0):
        provider = Provider(name, call, capabilities, priority)
        self.providers.append(provider)
        self.providers.sort(key=lambda p: -p.priority)
        return provider

    def unregister(self, name):
        self.providers = [p for p in self.providers if p.name != name]

    def route(self, capability="generate"):
        """The highest-priority provider offering a capability, or `None`.

        Routing by capability rather than by name means an application asks for
        what it needs, not for a specific vendor.
        """
        return next((p for p in self.providers if p.can(capability)), None)

    # -- prompts -----------------------------------------------------------

    def build_prompt(self, space_id, question, near=None, budget=2000, depth=1):
        """Assemble context and render it into a prompt.

        A prompt built from anything other than the Context Engine's output
        would bypass the budgeting, the provenance and the contradiction
        surfacing — so this is the only way a prompt gets built.
        """
        context = self.context.assemble(space_id, question=question, near=near,
                                        budget=budget, depth=depth)
        warning = CONFLICT_WARNING if context.contradictions() else ""
        prompt = PROMPT_TEMPLATE.format(
            conflict_warning=warning,
            context=context.render(),
            question=question or "Summarise what is known.",
        )
        return prompt, context

    # -- answering ---------------------------------------------------------

    def ask(self, space_id, question, near=None, budget=2000, depth=1,
            capability="generate", **options):
        """Answer a question about a space.

        With a provider registered, the model composes the answer from the
        assembled context. With none — or if the call fails — the context itself
        is returned, labelled `extractive`, with a note saying exactly why. Both
        paths are grounded in the graph; only the phrasing differs.
        """
        prompt, context = self.build_prompt(space_id, question, near=near,
                                            budget=budget, depth=depth)

        provider = self.route(capability)
        if provider is None:
            return Answer(
                text=self._extractive(context),
                mode="extractive",
                note="No AI provider is registered — answered directly from the graph.",
                context=context, prompt=prompt,
            )

        try:
            text = provider.call(prompt, **options)
        except Exception as e:
            return Answer(
                text=self._extractive(context),
                mode="extractive",
                note=f"Provider '{provider.name}' failed ({type(e).__name__}: {e}). "
                     "Answered directly from the graph instead.",
                context=context, provider=provider.name, prompt=prompt,
            )

        if not text or not str(text).strip():
            return Answer(
                text=self._extractive(context),
                mode="extractive",
                note=f"Provider '{provider.name}' returned nothing. "
                     "Answered directly from the graph instead.",
                context=context, provider=provider.name, prompt=prompt,
            )

        return Answer(text=str(text), mode="generative", context=context,
                      provider=provider.name, prompt=prompt)

    def _extractive(self, context):
        """The grounded answer: the assembled facts themselves.

        Not a placeholder or an apology — for most questions this is a genuinely
        useful answer, and it is always exactly as true as the graph.
        """
        if not context.fragments:
            return "Nothing relevant was found in this space."
        lines = []
        conflicts = context.contradictions()
        if conflicts:
            lines.append("The sources disagree:")
            lines.extend(f"  - {f.text}" for f in conflicts)
            lines.append("")
        lines.append("Based on what is recorded:")
        lines.extend(f"  - {f.text}" for f in context.fragments
                     if f.kind != "contradiction")
        return "\n".join(lines)
