"""Awarding the prize — who gets funded, and exactly how much.

The app awards a single winner a single number. That is the common case and it
is not the only one: most real briefs pay a runner-up, and some split a pot
across a shortlist. Once more than one person is paid, the arithmetic stops
being obvious — a £5,000 pot split 60/30/10 is fine, but 1/3 each is not, and
"about a third" is not an amount anyone can be paid.

So allocation goes through the platform's money splitter, which distributes by
largest remainder over integer pence and is guaranteed to reconstruct the pot
exactly. The alternative — rounding each placing independently — leaves pennies
unaccounted for, and a prize fund that does not balance is a prize fund somebody
will ask about.

## Awarding is gated on the phase, not on a flag

An award is only valid once entries have closed. Awarding while a challenge is
still open would mean judging a field that is not yet complete, and every
creator who had not submitted yet would be right to object. The phase is
computed from the clock, so this cannot be bypassed by forgetting to update a
status.
"""

from creativeos_engine.platform.money import split_pence, validate_split

#: Default shares when a sponsor funds more than one placing but does not say
#: how. Policy rather than fact, so it is stated where it can be seen and
#: overridden rather than buried in a function.
DEFAULT_PLACINGS = {
    1: [100],
    2: [70, 30],
    3: [60, 30, 10],
    4: [50, 25, 15, 10],
}


class AwardError(Exception):
    """Raised when a prize cannot be awarded as asked."""


class Award:
    """The decision, and the money it moves."""

    __slots__ = ("id", "challenge_id", "placings", "shares", "decided_at")

    def __init__(self, id, challenge_id, placings, shares, decided_at=None):
        self.id = id
        self.challenge_id = challenge_id
        #: `[submission_id, ...]` in placing order — winner first.
        self.placings = placings
        #: `[Share, ...]`, aligned with `placings`.
        self.shares = shares
        self.decided_at = decided_at

    @property
    def winner(self):
        return self.placings[0] if self.placings else None

    @property
    def total_pence(self):
        return sum(share.pence for share in self.shares)

    def describe(self):
        return " · ".join(
            f"{i + 1}. {sid} {share.describe()}"
            for i, (sid, share) in enumerate(zip(self.placings, self.shares)))

    def __repr__(self):
        return f"<Award {self.describe()}>"


def allocate(prize_pence, placings, split=None):
    """Divide a prize across placings. Returns `[Share, ...]`.

    `split` is `[percent, ...]` aligned with `placings`; omit it and
    `DEFAULT_PLACINGS` applies. The result always sums to `prize_pence`.
    """
    if not placings:
        raise AwardError("An award needs at least one placing.")
    if len(set(placings)) != len(placings):
        raise AwardError("The same entry cannot take two placings.")

    percents = list(split) if split else DEFAULT_PLACINGS.get(len(placings))
    if percents is None:
        raise AwardError(
            f"No default split for {len(placings)} placings — state one "
            f"explicitly. Guessing at how to divide a prize is not the engine's "
            f"decision to make.")
    if len(percents) != len(placings):
        raise AwardError(
            f"{len(percents)} shares were given for {len(placings)} placings.")

    pairs = list(zip(placings, percents))
    validate_split(pairs)
    return split_pence(prize_pence, pairs)


__all__ = ["Award", "AwardError", "allocate", "DEFAULT_PLACINGS"]
