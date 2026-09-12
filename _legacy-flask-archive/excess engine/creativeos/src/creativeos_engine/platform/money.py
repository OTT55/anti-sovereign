"""Splitting money so the parts always add up to the whole.

**Platform, not application.** This began inside RightsForge, splitting royalties
across contributors. CreatorStack then needed the identical thing to split a
prize across placings, and FilmCrew will need it for fees. The constitution's own
test settles it — *"can another application reuse this capability? If a
capability is universal, build it into CreativeOS"* — so it moved here rather
than being written a second time. Two applications rounding money by slightly
different rules is exactly the class of bug nobody finds until a payout is short.

The smallest module in the platform and the one most worth getting right,
because it is the only place in the ecosystem where being *approximately*
correct means somebody is short-changed.

Two rules, and everything follows from them.

**Integer pence, never floats.** `0.1 + 0.2 != 0.3` in binary floating point, and
a royalty ledger summed a few thousand times drifts far enough to be visible in
a payout. FrameVault already learned this and stores `amount_pence`; this engine
uses the same representation so no conversion sits between them.

**The parts must reconstruct the total exactly.** A 70/30 split of £10.01 is
700.7p and 300.3p, and neither rounding nor truncation gives back 1001p on its
own. So the split is computed by *largest remainder*: floor every share, then
hand the leftover pence out one at a time to whoever lost the most in the
flooring. That is deterministic, it never invents or loses a penny, and the
tie-break is by payee order so the same input always produces the same result.

The alternative — rounding each share independently — is what most systems do,
and it is wrong roughly half the time.
"""

#: Percentages are held as integers. A "0.5%" share is not representable, and
#: that is deliberate: allowing fractional percentages reintroduces exactly the
#: rounding problem this module exists to eliminate.
TOTAL_PERCENT = 100


class SplitError(Exception):
    """Raised when a split could not be honoured as written."""


class Share:
    """One payee's cut of a payment, in pence."""

    __slots__ = ("payee", "percent", "pence")

    def __init__(self, payee, percent, pence):
        self.payee = payee
        self.percent = percent
        self.pence = pence

    @property
    def pounds(self):
        return self.pence / 100

    def describe(self):
        return f"{self.payee}: £{self.pounds:,.2f} ({self.percent}%)"

    def __repr__(self):
        return f"<Share {self.describe()}>"

    def __eq__(self, other):
        return (isinstance(other, Share) and self.payee == other.payee
                and self.percent == other.percent and self.pence == other.pence)


def validate_split(split):
    """Check a `[(payee, percent), ...]` split before anything depends on it.

    Raises rather than returning a flag, because every caller's correct
    response to an invalid split is to refuse — a marketplace that accepts a
    97% split has silently decided who absorbs the missing 3%.
    """
    if not split:
        raise SplitError("A royalty split needs at least one payee.")

    seen = set()
    total = 0
    for payee, percent in split:
        name = (payee or "").strip()
        if not name:
            raise SplitError("Every share needs a named payee.")
        if name.casefold() in seen:
            raise SplitError(f"'{name}' appears twice in the split.")
        seen.add(name.casefold())
        if not isinstance(percent, int) or isinstance(percent, bool):
            raise SplitError(
                f"'{name}' has a non-integer share ({percent!r}). Percentages are "
                "whole numbers so a split cannot drift.")
        if percent <= 0:
            raise SplitError(f"'{name}' has a share of {percent}%, which pays nothing.")
        total += percent

    if total != TOTAL_PERCENT:
        raise SplitError(
            f"The split adds up to {total}%, not {TOTAL_PERCENT}%. "
            f"{'Somebody is owed' if total < TOTAL_PERCENT else 'The split promises'} "
            f"{abs(TOTAL_PERCENT - total)}% that nothing accounts for.")
    return True


def split_pence(amount_pence, split):
    """Divide `amount_pence` across a validated split. Returns `[Share, ...]`.

    Guaranteed: `sum(share.pence for share in result) == amount_pence`, exactly,
    for every input. That is the property the tests assert over thousands of
    combinations, because it is the only one that matters.
    """
    validate_split(split)
    if not isinstance(amount_pence, int) or isinstance(amount_pence, bool):
        raise SplitError("Amounts are integer pence — a float here is the bug "
                         "this module exists to prevent.")
    if amount_pence < 0:
        raise SplitError("A payment cannot be negative.")

    # Floor first, then distribute the remainder by who lost the most. Working
    # in scaled integers keeps the comparison exact; comparing float remainders
    # would reintroduce the drift at the very step meant to correct for it.
    floored = []
    for index, (payee, percent) in enumerate(split):
        scaled = amount_pence * percent
        floored.append({
            "index": index,
            "payee": payee,
            "percent": percent,
            "pence": scaled // TOTAL_PERCENT,
            "remainder": scaled % TOTAL_PERCENT,
        })

    leftover = amount_pence - sum(entry["pence"] for entry in floored)

    # Biggest shortfall first; ties broken by position, so the result is stable.
    order = sorted(floored, key=lambda e: (-e["remainder"], e["index"]))
    for entry in order[:leftover]:
        entry["pence"] += 1

    return [Share(e["payee"], e["percent"], e["pence"]) for e in floored]


def total_of(shares):
    return sum(share.pence for share in shares)


def to_pounds(pence):
    """Format for display. Money is only ever a string at the very edge."""
    return f"£{pence / 100:,.2f}"


def from_pounds(pounds):
    """Convert a price expressed in pounds to integer pence, once, at the edge.

    `round` rather than `int`: £29.99 arrives from JSON as 29.989999999999998,
    and truncating it bills the customer a penny less than the listed price.
    """
    return round(float(pounds) * 100)


__all__ = ["Share", "SplitError", "validate_split", "split_pence", "total_of",
           "to_pounds", "from_pounds", "TOTAL_PERCENT"]
