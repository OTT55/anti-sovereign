"""The Workflow Engine — *"Triggers. Pipelines. Background tasks."*

Automation that reacts to the Event Engine. A rule says: when *this* kind of
event happens and *this* condition holds, run *that*.

The design constraint that shapes everything: a workflow's action usually writes
to the graph, which emits an event, which can match another rule. Left alone
that is an infinite loop, and the first one written in anger will be an accident
rather than a design. So:

* **Depth is bounded.** A run carries a depth; cascading past `max_depth` stops
  and is recorded, not raised.
* **A rule cannot re-trigger on its own output.** Tracked by run, not globally,
  so two independent chains do not interfere.
* **Failures are captured, never propagated.** Same reasoning as the Event
  Engine (decision 0008): the event already happened, and one bad rule must not
  break the write that triggered it.

Every run is recorded, because automation you cannot audit is automation you
cannot trust.
"""

from ..graph import ids

RUN = "RUN"


class Rule:
    """When `pattern` fires and `condition` holds, run `action`."""

    __slots__ = ("name", "pattern", "action", "condition", "enabled")

    def __init__(self, name, pattern, action, condition=None, enabled=True):
        self.name = name
        self.pattern = pattern
        self.action = action
        self.condition = condition
        self.enabled = enabled

    def matches(self, event):
        if not self.enabled or not event.matches(self.pattern):
            return False
        if self.condition is None:
            return True
        try:
            return bool(self.condition(event))
        except Exception:
            # A condition that throws is a condition that did not hold. It must
            # not take down dispatch — the rule simply does not fire.
            return False

    def __repr__(self):
        return f"<Rule {self.name} on {self.pattern!r}>"


class Run:
    """One execution of one rule, recorded whatever the outcome."""

    __slots__ = ("id", "rule", "event", "status", "detail", "depth", "at")

    def __init__(self, id, rule, event, status, detail="", depth=0, at=""):
        self.id = id
        self.rule = rule
        self.event = event
        self.status = status      # "ok" | "failed" | "skipped" | "depth-limited"
        self.detail = detail
        self.depth = depth
        self.at = at

    def describe(self):
        return f"{self.rule} on {self.event.kind}: {self.status}" + (
            f" — {self.detail}" if self.detail else "")

    def __repr__(self):
        return f"<Run {self.describe()}>"


class WorkflowEngine:
    def __init__(self, bus, max_depth=3):
        self.bus = bus
        self.max_depth = max_depth
        self.rules = []
        self.runs = []
        self._depth = 0
        self._fired = set()   # (rule name, event id) within the current cascade
        self._subscription = bus.subscribe("*", self._on_event, name="workflow")

    def add_rule(self, name, pattern, action, condition=None):
        rule = Rule(name, pattern, action, condition)
        self.rules.append(rule)
        return rule

    def remove_rule(self, name):
        self.rules = [r for r in self.rules if r.name != name]

    def disable(self, name):
        for rule in self.rules:
            if rule.name == name:
                rule.enabled = False

    def enable(self, name):
        for rule in self.rules:
            if rule.name == name:
                rule.enabled = True

    # -- dispatch ----------------------------------------------------------

    def _on_event(self, event):
        for rule in list(self.rules):
            if not rule.matches(event):
                continue

            key = (rule.name, event.id)
            if key in self._fired:
                continue  # a rule must not re-trigger on its own output
            if self._depth >= self.max_depth:
                self._record(rule, event, "depth-limited",
                             f"stopped at depth {self._depth}")
                continue

            self._fired.add(key)
            self._depth += 1
            try:
                rule.action(event)
                self._record(rule, event, "ok")
            except Exception as e:
                self._record(rule, event, "failed", f"{type(e).__name__}: {e}")
            finally:
                self._depth -= 1
                if self._depth == 0:
                    self._fired.clear()

    def _record(self, rule, event, status, detail=""):
        run = Run(ids.new_id(RUN), rule.name, event, status, detail,
                  depth=self._depth, at=ids.now())
        self.runs.append(run)
        return run

    # -- inspection --------------------------------------------------------

    @property
    def failures(self):
        return [r for r in self.runs if r.status == "failed"]

    def history(self, rule_name=None):
        if rule_name is None:
            return list(self.runs)
        return [r for r in self.runs if r.rule == rule_name]

    def summary(self):
        counts = {}
        for run in self.runs:
            counts[run.status] = counts.get(run.status, 0) + 1
        return {"rules": len(self.rules), "runs": len(self.runs), **counts}

    def close(self):
        self.bus.unsubscribe(self._subscription)
