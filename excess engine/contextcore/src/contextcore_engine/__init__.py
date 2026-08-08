"""ContextCore — an organizational intelligence engine over a document corpus.

Documents in; entities, relationships, contradictions and answers-with-evidence
out. Deterministic except where a genuine judgement is needed, and there the
Claude-gated layer degrades honestly rather than guessing.

**The public interface.** Import from `contextcore_engine`, not from the modules
underneath — those are free to move, this is not. This is what Phase 1 of
`BUILD_PLAN.md` asks for: an explicit interface, so callers stop coupling
themselves to the package's internal layout.

The constitution's eight engines, and what backs each one:

    1 Ingestion      parse, chunk, dedupe, version, detect language
    2 Knowledge      extract entities, resolve duplicates, maintain an ontology
    3 Context        assemble passages for a question, within a budget
    4 Memory         version chains, and what the corpus stopped believing
    5 Reasoning      compare documents, trace a question across hops
    6 Verification   grounding, ambiguity, and the reasoning path
    7 Intelligence   the coordinator — the six questions over a corpus
    8 Domain         per-industry vocabulary and expectations, as data
"""

# -- the engine itself -----------------------------------------------------
from .engine import AskResult, ContextCoreEngine

# -- 1 Ingestion -----------------------------------------------------------
from .chunking import chunk_text, tokenize
from .ingestion import (
    IngestDecision, classify_incoming, content_hash, detect_language,
    diff_summary, extract_metadata, similarity,
)
from .parsers import SUPPORTED_EXTENSIONS, UnsupportedFormat, parse_file

# -- 2 Knowledge -----------------------------------------------------------
from .generation import (
    detect_conflict, extract_entities_relationships, generate_answer,
)
from .graph import build_graph, graph_svg
from .resolution import Cluster, Ontology, name_similarity, resolve

# -- 3 Context / 5 Reasoning / 6 Verification ------------------------------
from .reasoning import (
    Comparison, Context, Passage, ReasoningPath, ambiguous_terms, assemble,
    compare_documents, trace, verify_answer,
)

# -- 4 Memory --------------------------------------------------------------
from .memory import MemoryEngine

# -- retrieval and confidence (subsystems, not engines) --------------------
from .confidence import assess_confidence
from .retrieval import TFIDFIndex

# -- 7 Intelligence / 8 Domain --------------------------------------------
from . import domain
from .intelligence import CorpusBriefing, IntelligenceEngine

__all__ = [
    # the engine
    "ContextCoreEngine", "AskResult",
    # 1 ingestion
    "chunk_text", "tokenize", "parse_file", "SUPPORTED_EXTENSIONS",
    "UnsupportedFormat", "classify_incoming", "IngestDecision", "content_hash",
    "similarity", "detect_language", "extract_metadata", "diff_summary",
    # 2 knowledge
    "generate_answer", "detect_conflict", "extract_entities_relationships",
    "resolve", "Cluster", "Ontology", "name_similarity",
    "build_graph", "graph_svg",
    # 3/5/6 context, reasoning, verification
    "assemble", "Context", "Passage", "compare_documents", "Comparison",
    "trace", "verify_answer", "ambiguous_terms", "ReasoningPath",
    # 4 memory
    "MemoryEngine",
    # subsystems
    "TFIDFIndex", "assess_confidence",
    # 7/8 intelligence, domain
    "IntelligenceEngine", "CorpusBriefing", "domain",
]
