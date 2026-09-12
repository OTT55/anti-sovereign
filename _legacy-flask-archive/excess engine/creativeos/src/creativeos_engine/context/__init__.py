"""The Context Engine — *"Injects only necessary knowledge."*

Phase 5 of `BUILD_PLAN.md`. Assembles relevant knowledge for a question and fits
it to a budget, scoring by relevance × confidence × recency. Contradictions
bypass the budget and are always included.
"""

from .assembler import Context, ContextEngine, Fragment

__all__ = ["ContextEngine", "Context", "Fragment"]
