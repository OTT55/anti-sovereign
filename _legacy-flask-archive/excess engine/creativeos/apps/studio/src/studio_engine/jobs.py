"""Job orchestration — including the part where a job fails.

The app's schema documents four states in two places:

    status TEXT DEFAULT 'queued',   -- queued | running | done | failed

and its flow is `JOB_FLOW = ["queued", "running", "done"]`. Searching the whole
file, `failed` appears only in those two comments. **A job can never fail.** The
state is documented, reachable from nowhere, and every job that goes wrong
either sits in `running` forever or is quietly advanced to `done`.

That is worse than not modelling failure at all, because the schema promises a
distinction the API cannot make, and anything reading the table will believe it.

So this engine models both endings, and makes them different:

```
queued ──▶ running ──▶ done
               └─────▶ failed ──▶ (retry) ──▶ queued
```

* **done** is terminal and carries a result.
* **failed** is terminal, carries a *reason*, and can be retried — which starts
  a new attempt rather than resurrecting the old one, so the history keeps
  every attempt that was made.

A job that failed three times and succeeded on the fourth is a different fact
from a job that succeeded, and only one of them tells you the pipeline is sick.
"""

#: Forward progress. Retrying returns to the start, and that is a new attempt.
FLOW = ("queued", "running", "done")

#: Ended, one way or the other.
TERMINAL = ("done", "failed")


class JobError(Exception):
    """Raised when a job cannot move as asked."""


class Attempt:
    """One run at a job — kept even when it failed."""

    __slots__ = ("number", "state", "reason", "result", "started_at", "ended_at")

    def __init__(self, number, started_at=None):
        self.number = number
        self.state = "queued"
        self.reason = ""
        self.result = None
        self.started_at = started_at
        self.ended_at = None

    @property
    def is_finished(self):
        return self.state in TERMINAL

    def describe(self):
        tail = f" — {self.reason}" if self.reason else ""
        return f"attempt {self.number}: {self.state}{tail}"

    def __repr__(self):
        return f"<Attempt {self.describe()}>"


class Job:
    """A unit of orchestrated work, and every attempt at it."""

    __slots__ = ("id", "project_id", "kind", "attempts", "created_at")

    def __init__(self, id, project_id, kind, created_at=None):
        if not (kind or "").strip():
            raise JobError("A job needs a kind.")
        self.id = id
        self.project_id = project_id
        self.kind = kind
        self.created_at = created_at
        self.attempts = [Attempt(1, started_at=created_at)]

    @property
    def attempt(self):
        return self.attempts[-1]

    @property
    def state(self):
        return self.attempt.state

    @property
    def is_finished(self):
        return self.attempt.is_finished

    @property
    def succeeded(self):
        return self.attempt.state == "done"

    def advance(self, at=None, result=None):
        """One step forward. Never skips, never goes back.

        A job that can jump from `queued` to `done` has claimed work happened
        that nothing observed.
        """
        attempt = self.attempt
        if attempt.is_finished:
            raise JobError(
                f"This job already {attempt.state}. Retry it to run again.")
        attempt.state = FLOW[FLOW.index(attempt.state) + 1]
        if attempt.state == "done":
            attempt.result = result
            attempt.ended_at = at
        return self

    def fail(self, reason, at=None):
        """End this attempt badly, with a reason.

        The reason is required. "Failed" with no explanation is a dead end for
        whoever has to work out why, and the moment it is optional it is always
        omitted.
        """
        if not (reason or "").strip():
            raise JobError(
                "A failure needs a reason — 'failed' on its own tells whoever "
                "picks this up nothing they can act on.")
        attempt = self.attempt
        if attempt.is_finished:
            raise JobError(f"This job already {attempt.state}.")
        attempt.state = "failed"
        attempt.reason = reason
        attempt.ended_at = at
        return self

    def retry(self, at=None):
        """Start a fresh attempt. Only after a failure.

        A new attempt rather than resetting the old one, so the record keeps
        every run. A job that failed three times and then worked is a different
        fact from a job that worked, and only one of them says the pipeline is
        sick.
        """
        if self.attempt.state != "failed":
            raise JobError(
                f"Only a failed job can be retried; this one is "
                f"{self.attempt.state}.")
        self.attempts.append(Attempt(len(self.attempts) + 1, started_at=at))
        return self

    @property
    def failures(self):
        return [a for a in self.attempts if a.state == "failed"]

    def describe(self):
        tail = (f" ({len(self.attempts)} attempts)" if len(self.attempts) > 1
                else "")
        return f"{self.kind}: {self.state}{tail}"

    def __repr__(self):
        return f"<Job {self.describe()}>"


__all__ = ["Job", "Attempt", "JobError", "FLOW", "TERMINAL"]
