"""The Creative Knowledge Graph — the substrate every CreativeOS engine shares.

Not one of Constitution v2.0's fourteen core engines: it is what the Knowledge,
Identity, Graph, Memory, Context and Verification engines are all built out of.
Everything else in CreativeOS reads and writes through here.
"""

from .graph import CreativeGraph, GraphError
from .model import (
    Assertion, AssertionKind, Contradiction, Entity, Space, ValidWindow,
)
from .store import GraphStore
from .types import DomainPack, TypeError_, normalize_type

__all__ = [
    "CreativeGraph", "GraphError", "GraphStore",
    "Assertion", "AssertionKind", "Contradiction", "Entity", "Space", "ValidWindow",
    "DomainPack", "TypeError_", "normalize_type",
]
