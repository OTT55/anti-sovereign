"""Challenges, submissions, and the rules that make a competition fair.

CreatorStack's domain authority. A brand posts a brief, creators submit, the
sponsor picks a winner, and the winner gets funded. The engine's job is the part
that has to be defensible when somebody loses and objects.

## The deadline is a fact about time, not a status somebody remembers to flip

This is the same lesson RightsForge's option term taught, and it shows up here
in a worse place. The app stores `submit_deadline` as a column and **never
compares it to anything** — it only checks `status != "open"`. So a submission
sent a week after the deadline is accepted, as long as nobody has manually moved
the challenge to `judging`.

That is not a tidiness problem. A competition that accepted a late entry and
then awarded a prize is a competition whose result can be challenged by every
entrant who made the deadline.

So `phase()` is **computed** from the clock, never stored:

```
open      the deadline has not passed
judging   the deadline has passed, no award yet
awarded   an award exists
```

Nothing has to run at midnight. There is no job to forget.

## Eligibility is checked once, in one place

Three rules, and every one of them is the kind of thing that gets noticed only
after it has been exploited:

* a sponsor may not enter their own challenge,
* one entry per creator per challenge,
* no entry after the deadline.

## A submission is fixed once it is in

Every submission carries a content hash. After the deadline it cannot be
replaced — not because anyone is expected to cheat, but because "the file I
judged is the file they sent" has to be checkable without anyone's word for it.
"""

import hashlib

#: The phases a challenge moves through. Derived, never assigned.
PHASES = ("open", "judging", "awarded")


class CompetitionError(Exception):
    """Raised when a competition rule would be broken."""


def content_hash(data):
    """SHA-256 of exactly what was submitted.

    Bytes in, hex out. A submission's identity is its content, so an edited file
    is a different submission and says so.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


class Submission:
    """One creator's entry."""

    __slots__ = ("id", "challenge_id", "creator", "pitch", "hash", "submitted_at")

    def __init__(self, id, challenge_id, creator, pitch, hash="", submitted_at=None):
        self.id = id
        self.challenge_id = challenge_id
        self.creator = creator
        self.pitch = pitch
        self.hash = hash
        self.submitted_at = submitted_at

    def describe(self):
        return f"{self.creator}: {self.pitch[:48]}"

    def __repr__(self):
        return f"<Submission {self.describe()}>"


class Challenge:
    """A brief, a prize, and a deadline."""

    __slots__ = ("id", "sponsor", "title", "brief", "prize_pence", "deadline",
                 "created_at")

    def __init__(self, id, sponsor, title, brief="", prize_pence=0, deadline=None,
                 created_at=None):
        if not (sponsor or "").strip():
            raise CompetitionError("A challenge needs a sponsor.")
        if not (title or "").strip():
            raise CompetitionError("A challenge needs a title.")
        if prize_pence < 0:
            raise CompetitionError("A prize cannot be negative.")
        if deadline is None:
            raise CompetitionError(
                "A challenge needs a deadline. Without one there is no moment at "
                "which entries close, so 'late' has no meaning and no result is "
                "defensible.")
        self.id = id
        self.sponsor = sponsor
        self.title = title
        self.brief = brief
        self.prize_pence = prize_pence
        self.deadline = deadline
        self.created_at = created_at

    def is_open(self, now):
        return now <= self.deadline

    def describe(self):
        return f"{self.title} — {self.sponsor} — closes {self.deadline}"

    def __repr__(self):
        return f"<Challenge {self.describe()}>"


class CreatorStack:
    """Challenges, submissions and the rules between them.

    Publishes events and holds no reference to FrameVault or any other
    application, exactly like FilmCrew and RightsForge.
    """

    def __init__(self, bus=None, space_id="", source="creatorstack"):
        self.bus = bus
        self.space_id = space_id
        self.source = source
        self.challenges = {}
        self.submissions = {}
        self.awards = {}
        self._next = 1

    def _id(self, prefix):
        value = f"{prefix}-{self._next:05d}"
        self._next += 1
        return value

    def _publish(self, kind, subject_id, payload):
        if self.bus is None:
            return None
        return self.bus.publish(self.space_id, kind, subject_id, payload,
                                source=self.source)

    # -- challenges --------------------------------------------------------

    def post_challenge(self, sponsor, title, brief="", prize_pence=0,
                       deadline=None, now=None):
        challenge = Challenge(self._id("C"), sponsor, title, brief, prize_pence,
                              deadline, created_at=now)
        self.challenges[challenge.id] = challenge
        self._publish("challenge.posted", challenge.id,
                      {"title": title, "sponsor": sponsor,
                       "prize_pence": prize_pence, "deadline": deadline})
        return challenge

    def phase(self, challenge_id, now):
        """Where a challenge is, computed from the clock and the awards.

        Never stored, so it cannot be stale and cannot be wrong because somebody
        forgot to update it.
        """
        challenge = self._challenge(challenge_id)
        if challenge_id in self.awards:
            return "awarded"
        return "open" if challenge.is_open(now) else "judging"

    # -- submitting --------------------------------------------------------

    def submit(self, challenge_id, creator, pitch, data=None, now=None):
        """Enter a challenge, or be told exactly why not."""
        challenge = self._challenge(challenge_id)

        if now is None:
            raise CompetitionError(
                "A submission needs a time, so it can be checked against the "
                "deadline.")
        if not challenge.is_open(now):
            raise CompetitionError(
                f"'{challenge.title}' closed at {challenge.deadline}. This "
                f"arrived at {now}. Accepting it would make the result "
                "challengeable by everyone who made the deadline.")
        if creator == challenge.sponsor:
            raise CompetitionError(
                "A sponsor cannot enter their own challenge — they choose the "
                "winner.")
        if any(s.creator == creator for s in self.entries(challenge_id)):
            raise CompetitionError(f"{creator} has already entered this challenge.")
        if not (pitch or "").strip() and data is None:
            raise CompetitionError("A submission needs a pitch or a file.")

        submission = Submission(
            self._id("S"), challenge_id, creator, pitch,
            hash=content_hash(data) if data is not None else content_hash(pitch),
            submitted_at=now)
        self.submissions[submission.id] = submission
        self._publish("submission.received", submission.id,
                      {"challenge": challenge_id, "creator": creator,
                       "hash": submission.hash})
        return submission

    def entries(self, challenge_id):
        return [s for s in self.submissions.values()
                if s.challenge_id == challenge_id]

    def verify(self, submission_id, data):
        """Is this the file that was submitted?

        Not an accusation mechanism — a way for "the entry I judged is the entry
        they sent" to be checkable without taking anyone's word for it.
        """
        submission = self._submission(submission_id)
        return content_hash(data) == submission.hash

    # -- awarding ----------------------------------------------------------

    def award(self, challenge_id, placings, by, now, split=None):
        """Award the prize. Only the sponsor, only once, only after entries close.

        The `challenge.won` event is published **after** the award is recorded,
        so a listener that reacts by asking who won cannot arrive before the
        answer exists — the same ordering RightsForge uses for grants.
        """
        from .awards import Award, AwardError, allocate

        challenge = self._challenge(challenge_id)
        phase = self.phase(challenge_id, now)

        if by != challenge.sponsor:
            raise AwardError(
                f"Only {challenge.sponsor} can award this challenge.")
        if phase == "awarded":
            raise AwardError("This challenge has already been awarded.")
        if phase == "open":
            raise AwardError(
                f"'{challenge.title}' is still open until {challenge.deadline}. "
                "Awarding now would judge a field that is not yet complete.")

        entries = {s.id for s in self.entries(challenge_id)}
        if not entries:
            raise AwardError("Nothing was submitted to this challenge.")
        for submission_id in placings:
            if submission_id not in entries:
                raise AwardError(
                    f"'{submission_id}' was not submitted to this challenge.")

        shares = allocate(challenge.prize_pence, placings, split)
        award = Award(self._id("A"), challenge_id, list(placings), shares,
                      decided_at=now)
        self.awards[challenge_id] = award

        for placing, (submission_id, share) in enumerate(zip(placings, shares), 1):
            submission = self._submission(submission_id)
            self._publish("challenge.won", submission_id, {
                "challenge": challenge_id,
                "title": challenge.title,
                "sponsor": challenge.sponsor,
                "creator": submission.creator,
                "placing": placing,
                "amount_pence": share.pence,
            })
        return award

    def winner_of(self, challenge_id):
        award = self.awards.get(challenge_id)
        return award.winner if award else None

    # -- lookups -----------------------------------------------------------

    def _challenge(self, challenge_id):
        challenge = self.challenges.get(challenge_id)
        if challenge is None:
            raise CompetitionError(f"Unknown challenge '{challenge_id}'.")
        return challenge

    def _submission(self, submission_id):
        submission = self.submissions.get(submission_id)
        if submission is None:
            raise CompetitionError(f"Unknown submission '{submission_id}'.")
        return submission

    def summary(self, now):
        return {
            "challenges": len(self.challenges),
            "open": sum(1 for c in self.challenges
                        if self.phase(c, now) == "open"),
            "judging": sum(1 for c in self.challenges
                           if self.phase(c, now) == "judging"),
            "awarded": len(self.awards),
            "submissions": len(self.submissions),
        }


__all__ = ["CreatorStack", "Challenge", "Submission", "CompetitionError",
           "content_hash", "PHASES"]
