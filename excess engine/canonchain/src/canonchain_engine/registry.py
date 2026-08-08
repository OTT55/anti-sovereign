"""The registry: who registered these exact bytes first, and how to prove it.

Canonchain answers one narrow, provable question — *who held this file first?* —
and refuses the broader one it cannot answer. Registering a hash proves you had
those bytes at that time. It does **not** prove you made them, and this engine
never claims otherwise.

## What it will and will not say

| Question | Answer |
|---|---|
| Was this exact file registered, and when? | yes, with a proof |
| Who registered it first? | yes — the earliest leaf wins, by position |
| Did they create it? | **no.** Registering somebody else's file records that you held it, nothing more |

The third row is why `first_claim()` returns the earliest registration rather
than "the owner". An engine that upgrades a timestamp into authorship is making
a legal claim out of an ordering fact.

## Append-only, and checkable

Leaves are only ever added, never reordered or removed, so every previously
issued proof stays valid forever. A checkpoint signs `(leaf_count, root)`, and
`merkle.consistent()` lets anyone confirm a later checkpoint genuinely extends
an earlier one rather than quietly rewriting it — the question a published root
invites and which the app has no way to answer.

## On signing

`HMACSigner` is symmetric and therefore **test-only**, for the same reason
Veridact says so: a verifier that could forge a signature is not a witness. A
registry whose operator can mint checkpoints is asking to be trusted, which is
precisely what a cryptographic registry exists to avoid. Real deployments sign
checkpoints with a key the registry does not hold.
"""

import hashlib
import hmac

from . import merkle


class RegistryError(Exception):
    """Raised when a registration cannot be made."""


class DuplicateRegistration(RegistryError):
    """These exact bytes are already registered.

    Its own type because it is not really an error — it is the registry working.
    The caller usually wants to show the *existing* claim, so it carries it.
    """

    def __init__(self, message, existing=None):
        super().__init__(message)
        self.existing = existing


def file_hash(data):
    """SHA-256 of the file itself. The registry never sees the file.

    Registering a hash discloses nothing about the content, which is what makes
    it safe to register an unreleased work.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


class Registration:
    """One work, one leaf."""

    __slots__ = ("registry_id", "creator", "file_hash", "filename",
                 "description", "leaf_index", "registered_at", "signature")

    def __init__(self, registry_id, creator, file_hash, filename="",
                 description="", leaf_index=0, registered_at=None, signature=""):
        self.registry_id = registry_id
        self.creator = creator
        self.file_hash = file_hash
        self.filename = filename
        self.description = description
        self.leaf_index = leaf_index
        self.registered_at = registered_at
        self.signature = signature

    def describe(self):
        return (f"{self.registry_id} — {self.filename or '(unnamed)'} — "
                f"{self.creator} — leaf {self.leaf_index}")

    def __repr__(self):
        return f"<Registration {self.describe()}>"


class Checkpoint:
    """A signed snapshot of the whole registry at a moment."""

    __slots__ = ("leaf_count", "root", "at", "signature")

    def __init__(self, leaf_count, root, at=None, signature=""):
        self.leaf_count = leaf_count
        self.root = root
        self.at = at
        self.signature = signature

    def describe(self):
        return f"{self.leaf_count} leaves — root {self.root[:16]}…"

    def __repr__(self):
        return f"<Checkpoint {self.describe()}>"


class HMACSigner:
    """Symmetric signing. **Test-only, and it says so.**

    `is_asymmetric` is `False` so nothing mistakes it for production-grade. A
    registry that can forge its own checkpoints is asking to be trusted, and a
    cryptographic registry exists so that nobody has to.
    """

    is_asymmetric = False
    algorithm = "hmac-sha256"

    def __init__(self, key=b"canonchain-test-key"):
        self.key = key

    def sign(self, message):
        return hmac.new(self.key, message.encode(), hashlib.sha256).hexdigest()

    def verify(self, message, signature):
        return hmac.compare_digest(self.sign(message), signature or "")


class Canonchain:
    """The registry. In-memory by design — persistence is the app's job."""

    def __init__(self, signer=None, clock=None):
        self.signer = signer or HMACSigner()
        self._clock = clock or (lambda: None)
        self.registrations = []
        self._by_hash = {}
        self.checkpoints = []

    # -- registering -------------------------------------------------------

    def register(self, creator, digest, filename="", description="", at=None):
        """Record a claim over these exact bytes.

        Refuses a repeat rather than adding a second leaf. Two leaves with the
        same value would put two competing first-claims in the tree, and the
        registry's only real assertion is that there is exactly one.
        """
        if not (creator or "").strip():
            raise RegistryError("A registration needs a creator.")
        digest = (digest or "").strip().lower()
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise RegistryError(
                "A file hash is 64 hex characters of SHA-256. Registering "
                "anything else would put a value in the tree that no file "
                "produces.")

        existing = self._by_hash.get(digest)
        if existing is not None:
            raise DuplicateRegistration(
                f"These exact bytes are already registered as "
                f"{existing.registry_id} by {existing.creator}"
                f"{f' on {existing.registered_at}' if existing.registered_at else ''}.",
                existing=existing)

        at = at if at is not None else self._clock()
        index = len(self.registrations)
        registration = Registration(
            registry_id=f"CC-{index + 1:08d}",
            creator=creator, file_hash=digest, filename=filename,
            description=description, leaf_index=index, registered_at=at)
        registration.signature = self.signer.sign(self._message(registration))

        self.registrations.append(registration)
        self._by_hash[digest] = registration
        return registration

    @staticmethod
    def _message(registration):
        """Everything the signature covers.

        The whole record, not a convenient subset. A signature over some of the
        fields leaves the rest editable without breaking it, which reads as
        tamper-evidence while providing none.
        """
        return "|".join(str(part) for part in (
            registration.registry_id, registration.creator,
            registration.file_hash, registration.filename,
            registration.description, registration.leaf_index,
            registration.registered_at))

    def seal_intact(self, registration):
        """Has this record been altered since it was signed?"""
        return self.signer.verify(self._message(registration),
                                  registration.signature)

    # -- proving -----------------------------------------------------------

    @property
    def leaves(self):
        return [r.file_hash for r in self.registrations]

    def root(self):
        return merkle.root(self.leaves)

    def proof_for(self, digest):
        """An inclusion proof for these bytes, or `None` if never registered."""
        registration = self._by_hash.get((digest or "").strip().lower())
        if registration is None:
            return None
        return {
            "registry_id": registration.registry_id,
            "leaf": registration.file_hash,
            "leaf_index": registration.leaf_index,
            "path": merkle.proof(self.leaves, registration.leaf_index),
            "root": self.root(),
        }

    def verify(self, digest, proof, expected_root=None):
        """Check a proof without consulting the registry.

        Takes the root as an argument so a third party can verify against a root
        they obtained elsewhere — from a signed checkpoint, a newspaper, another
        mirror. A proof that can only be checked by asking the registry whether
        the registry is honest proves nothing.
        """
        return merkle.verify(digest, proof, expected_root or self.root())

    # -- looking up --------------------------------------------------------

    def find(self, digest):
        return self._by_hash.get((digest or "").strip().lower())

    def first_claim(self, digest):
        """Who registered these bytes first — an ordering fact, not authorship.

        Deliberately not called `owner_of`. The registry knows who held the
        bytes earliest; turning that into a claim about who made them is a legal
        assertion it has no basis for.
        """
        return self.find(digest)

    def registrations_by(self, creator):
        return [r for r in self.registrations if r.creator == creator]

    # -- checkpoints -------------------------------------------------------

    def checkpoint(self, at=None):
        """Sign the current state, so the root is anchored in time."""
        current = self.root()
        if current is None:
            raise RegistryError("An empty registry has no root to check-point.")
        at = at if at is not None else self._clock()
        checkpoint = Checkpoint(len(self.registrations), current, at=at)
        checkpoint.signature = self.signer.sign(
            f"{checkpoint.leaf_count}|{checkpoint.root}|{at}")
        self.checkpoints.append(checkpoint)
        return checkpoint

    def checkpoint_valid(self, checkpoint):
        return self.signer.verify(
            f"{checkpoint.leaf_count}|{checkpoint.root}|{checkpoint.at}",
            checkpoint.signature)

    def extends(self, earlier):
        """Does the registry today genuinely extend that earlier checkpoint?

        Confirms nothing was reordered or removed since. A registry that
        rewrote history would publish a new root, and without this check nobody
        could tell that apart from honest growth — which is the entire value of
        publishing a root at all.
        """
        if earlier.leaf_count > len(self.registrations):
            return False
        prefix = self.leaves[:earlier.leaf_count]
        return merkle.root(prefix) == earlier.root

    def summary(self):
        return {
            "registrations": len(self.registrations),
            "creators": len({r.creator for r in self.registrations}),
            "checkpoints": len(self.checkpoints),
            "root": self.root(),
        }


__all__ = ["Canonchain", "Registration", "Checkpoint", "HMACSigner",
           "RegistryError", "DuplicateRegistration", "file_hash"]
