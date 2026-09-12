"""FilmCrew Engine — the domain authority for production.

    Production   productions, stages, casting and the contract lifecycle

The rule FilmCrew owns: credit fires on `paid`, not on `hired`. An offer can be
withdrawn and a shoot can collapse; money changing hands is the first moment the
work is evidenced.

FilmCrew publishes `hire.completed` and holds no reference to any listener.
"""

from .production import (
    CONTRACT_STATES, STAGES, Contract, PipelineError, Production, ProductionEngine,
)

__all__ = [
    "ProductionEngine", "Production", "Contract", "PipelineError",
    "STAGES", "CONTRACT_STATES",
]
