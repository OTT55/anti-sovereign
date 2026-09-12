"""CreatorStack Engine — the domain authority for competitions.

Sits on top of CreativeOS. CreativeOS understands connections; CreatorStack
understands that a deadline is a fact about time rather than a status somebody
remembers to flip, that a creator voting for themselves is not a signal, and
that a prize split across three placings has to add up to the prize.

Three modules, one idea each:

* `competition` — challenges, submissions, eligibility, and the computed phase
* `ballot`      — voting, and the evidence that separates support from a brigade
* `awards`      — dividing a prize so the placings reconstruct the pot exactly

Deterministic and self-contained. It publishes events and holds no reference to
FrameVault or to any other application.

    from creatorstack_engine import CreatorStack, Ballot

    stack = CreatorStack()
    brief = stack.post_challenge("nova-films", "60 seconds of dread",
                                 prize_pence=500_000, deadline=30)
    entry = stack.submit(brief.id, "ott", "A corridor. One light.", now=10)

    stack.phase(brief.id, now=10)    # "open"
    stack.phase(brief.id, now=31)    # "judging" — nothing had to run
    stack.award(brief.id, [entry.id], by="nova-films", now=31)
"""

from .awards import DEFAULT_PLACINGS, Award, AwardError, allocate
from .ballot import CONCENTRATION_FLAG, SINGLE_USE_VOTES, Ballot, BallotError, Tally
from .competition import (
    PHASES, Challenge, CompetitionError, CreatorStack, Submission, content_hash,
)

__all__ = [
    # competition
    "CreatorStack", "Challenge", "Submission", "CompetitionError",
    "content_hash", "PHASES",
    # voting
    "Ballot", "Tally", "BallotError", "SINGLE_USE_VOTES", "CONCENTRATION_FLAG",
    # awards
    "Award", "AwardError", "allocate", "DEFAULT_PLACINGS",
]
