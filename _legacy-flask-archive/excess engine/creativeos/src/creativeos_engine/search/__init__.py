"""The Search Engine — *"Everything searchable."*

Phase 4 of `BUILD_PLAN.md`. Keyword (TF-IDF), relationship, traversal and
timeline retrieval over the graph, plus a hybrid rank. Deterministic, no model.
"""

from .engine import Hit, SearchEngine
from .index import SearchIndex, tokenize

__all__ = ["SearchEngine", "SearchIndex", "Hit", "tokenize"]
