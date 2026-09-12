"""Community voting, and how to tell a signal from a brigade.

The app's voting is honest as far as it goes: one vote per FrameVault identity
per submission, enforced by a unique constraint. Two things are missing, and
both are the kind that only get noticed after somebody exploits them.

**A creator can vote for their own entry, and so can the sponsor.** Nothing
checks. In a competition where votes are *"the signal the sponsor sees when
picking a winner"*, a self-vote is a thumb on the scale, and a sponsor voting
before judging is worse than that.

**A raw count cannot tell enthusiasm from coordination.** Twenty votes from
twenty people who also voted on other entries is a result. Twenty votes from
twenty accounts that have never voted for anything else is a brigade, and both
render as "20".

## Why the engine reports rather than discounts

It would be easy to silently down-weight suspicious votes. That is the wrong
call, for the same reason StoryAtlas offers both resolutions to a contradiction
instead of picking one: **disqualifying somebody's votes is an accusation**, and
an engine that makes it silently is one nobody can argue with.

So `integrity()` returns evidence — how concentrated the support is, how many
voters have never voted on anything else, whether the creator voted for
themselves — and a human decides. Every signal cites the numbers behind it.

The thresholds are named constants rather than buried literals, because they are
policy, not fact, and whoever runs the competition should be able to see and
change them.
"""

from collections import defaultdict

#: A voter who has cast this many votes or fewer, all on one entry, contributes
#: no evidence that the entry is good — they may simply be a friend. Not proof
#: of anything on its own; it is the *proportion* of such voters that matters.
SINGLE_USE_VOTES = 1

#: Above this share of single-use voters, an entry's support is worth a look.
#: Policy, not fact.
CONCENTRATION_FLAG = 0.6


class BallotError(Exception):
    """Raised when a vote cannot be cast."""


class Tally:
    """One submission's support, and what the votes look like underneath."""

    __slots__ = ("submission_id", "votes", "voters", "single_use", "self_voted")

    def __init__(self, submission_id, votes, voters, single_use, self_voted):
        self.submission_id = submission_id
        self.votes = votes
        self.voters = voters
        #: Voters who have voted for nothing else in the whole competition.
        self.single_use = single_use
        self.self_voted = self_voted

    @property
    def concentration(self):
        """The share of support coming from voters who voted for nothing else.

        1.0 means every supporter turned up for this entry alone.
        """
        return self.single_use / self.votes if self.votes else 0.0

    @property
    def is_concentrated(self):
        return self.votes > 0 and self.concentration >= CONCENTRATION_FLAG

    def describe(self):
        note = ""
        if self.is_concentrated:
            note = (f"  ⚠ {self.single_use}/{self.votes} voters voted for "
                    f"nothing else")
        return f"{self.submission_id}: {self.votes} votes{note}"

    def __repr__(self):
        return f"<Tally {self.describe()}>"


class Ballot:
    """The votes cast in one challenge.

    Held per challenge rather than globally, because "has this voter voted for
    anything else" only means something inside a single competition — a voter
    who is active across the platform but turned up once here is exactly the
    pattern worth seeing.
    """

    def __init__(self, challenge_id):
        self.challenge_id = challenge_id
        self._votes = defaultdict(set)      # submission_id -> {voter}

    # -- casting -----------------------------------------------------------

    def cast(self, submission, voter, sponsor=None, now=None, challenge=None):
        """Record a vote, or refuse it with a reason.

        `submission` is a `Submission`; `sponsor` the challenge's sponsor. Both
        are passed rather than looked up so the ballot stays a pure record and
        does not need to reach back into the competition.
        """
        if not (voter or "").strip():
            raise BallotError("A vote needs a voter.")
        if voter == submission.creator:
            raise BallotError(
                "A creator cannot vote for their own entry. Votes are the signal "
                "the sponsor judges on, and a self-vote is a thumb on the scale.")
        if sponsor is not None and voter == sponsor:
            raise BallotError(
                "The sponsor cannot vote. They pick the winner, and voting first "
                "would let them appear to be following a signal they created.")
        if challenge is not None and now is not None and challenge.is_open(now):
            pass    # voting during the open phase is fine; stated for clarity
        if voter in self._votes[submission.id]:
            raise BallotError(f"{voter} has already voted for this entry.")

        self._votes[submission.id].add(voter)
        return True

    def withdraw(self, submission_id, voter):
        """Un-vote. Returns whether there was a vote to remove."""
        if voter in self._votes.get(submission_id, ()):
            self._votes[submission_id].discard(voter)
            return True
        return False

    def has_voted(self, submission_id, voter):
        return voter in self._votes.get(submission_id, ())

    # -- reading -----------------------------------------------------------

    def count(self, submission_id):
        return len(self._votes.get(submission_id, ()))

    def _votes_per_voter(self):
        totals = defaultdict(int)
        for voters in self._votes.values():
            for voter in voters:
                totals[voter] += 1
        return totals

    def tally(self, submissions):
        """A `Tally` per submission, richest-first, with the integrity evidence.

        Sorted by raw votes, deliberately. Reordering entries by a
        trustworthiness score would hide the disagreement between "most votes"
        and "most credible votes", and that disagreement is the whole point.
        """
        totals = self._votes_per_voter()
        out = []
        for submission in submissions:
            voters = sorted(self._votes.get(submission.id, ()))
            single = sum(1 for v in voters if totals[v] <= SINGLE_USE_VOTES)
            out.append(Tally(
                submission_id=submission.id,
                votes=len(voters),
                voters=voters,
                single_use=single,
                self_voted=submission.creator in voters,
            ))
        return sorted(out, key=lambda t: (-t.votes, t.submission_id))

    def integrity(self, submissions):
        """Everything worth a human's attention, with the numbers behind it.

        Returns `[{...}]`, empty when nothing stands out. Evidence, not verdicts:
        disqualifying somebody's votes is an accusation, and an engine that makes
        it silently is one nobody can argue with.
        """
        findings = []
        for tally in self.tally(submissions):
            if tally.self_voted:
                findings.append({
                    "submission": tally.submission_id,
                    "signal": "self-vote",
                    "detail": "The creator voted for their own entry.",
                })
            if tally.is_concentrated:
                findings.append({
                    "submission": tally.submission_id,
                    "signal": "concentrated-support",
                    "detail": (
                        f"{tally.single_use} of {tally.votes} voters voted for "
                        f"nothing else in this challenge "
                        f"({tally.concentration:.0%})."),
                    "concentration": round(tally.concentration, 3),
                })
        return findings

    def leader(self, submissions):
        """The entry with the most votes, or `None` on a tie or an empty ballot.

        A tie returns nothing rather than picking one. There is no honest way to
        break it here, and quietly choosing the lower id would be a result
        decided by insertion order.
        """
        ranked = self.tally(submissions)
        if not ranked or ranked[0].votes == 0:
            return None
        if len(ranked) > 1 and ranked[1].votes == ranked[0].votes:
            return None
        return ranked[0]

    def summary(self):
        return {
            "submissions_voted_on": sum(1 for v in self._votes.values() if v),
            "votes": sum(len(v) for v in self._votes.values()),
            "voters": len(self._votes_per_voter()),
        }


__all__ = ["Ballot", "Tally", "BallotError", "SINGLE_USE_VOTES",
           "CONCENTRATION_FLAG"]
