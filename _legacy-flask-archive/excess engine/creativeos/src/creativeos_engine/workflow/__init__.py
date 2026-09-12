"""The Workflow Engine — *"Triggers. Pipelines. Background tasks."*

Part of Phase 10. Event-driven rules with bounded cascade depth, loop
prevention, and an audit trail of every run.
"""

from .engine import Rule, Run, WorkflowEngine

__all__ = ["WorkflowEngine", "Rule", "Run"]
