"""Registrations, first claims, proofs and checkpoints."""

import pytest

from canonchain_engine import (
    Canonchain, DuplicateRegistration, HMACSigner, RegistryError, file_hash,
)


@pytest.fixture
def chain():
    return Canonchain()


@pytest.fixture
def stocked(chain):
    for i in range(5):
        chain.register("ott", file_hash(f"work {i}".encode()),
                       filename=f"work{i}.mov", at=f"day-{i}")
    return chain


# -- registering ------------------------------------------------------------

def test_a_registration_takes_the_next_leaf(chain):
    first = chain.register("ott", file_hash(b"one"))
    second = chain.register("kestrel", file_hash(b"two"))
    assert (first.leaf_index, second.leaf_index) == (0, 1)


def test_the_registry_never_sees_the_file(chain):
    """Registering a hash discloses nothing about the content, which is what
    makes it safe to register an unreleased work."""
    digest = file_hash(b"a secret script")
    entry = chain.register("ott", digest)
    assert entry.file_hash == digest
    assert "secret" not in repr(entry)


def test_the_same_bytes_cannot_be_registered_twice(chain):
    """Two leaves with the same value would put two competing first-claims in
    the tree, and the registry's only real assertion is that there is one."""
    digest = file_hash(b"one")
    chain.register("ott", digest)
    with pytest.raises(DuplicateRegistration) as caught:
        chain.register("kestrel", digest)
    assert caught.value.existing.creator == "ott"


def test_the_duplicate_carries_the_existing_claim(chain):
    """It is not really an error — it is the registry working, and the caller
    usually wants to show who got there first."""
    digest = file_hash(b"one")
    chain.register("ott", digest, at="1999")
    try:
        chain.register("kestrel", digest)
    except DuplicateRegistration as error:
        assert "ott" in str(error) and "1999" in str(error)


def test_something_that_is_not_a_hash_is_refused(chain):
    """Registering anything else puts a value in the tree that no file
    produces."""
    for bad in ("", "not-a-hash", "ab" * 10, "zz" * 32):
        with pytest.raises(RegistryError, match="64 hex characters"):
            chain.register("ott", bad)


def test_a_registration_needs_a_creator(chain):
    with pytest.raises(RegistryError, match="needs a creator"):
        chain.register("  ", file_hash(b"one"))


def test_a_hash_is_matched_regardless_of_case(chain):
    digest = file_hash(b"one")
    chain.register("ott", digest)
    assert chain.find(digest.upper()) is not None


# -- what it will and will not claim -----------------------------------------

def test_first_claim_is_the_earliest_registration(stocked):
    digest = file_hash(b"work 0")
    assert stocked.first_claim(digest).leaf_index == 0


def test_first_claim_is_an_ordering_fact_not_authorship(chain):
    """Deliberately not called `owner_of`. Turning a timestamp into a claim
    about who *made* something is a legal assertion the registry cannot support.
    """
    assert not hasattr(chain, "owner_of")
    assert chain.first_claim(file_hash(b"never registered")) is None


def test_a_creator_can_list_their_own_registrations(stocked):
    stocked.register("kestrel", file_hash(b"theirs"))
    assert len(stocked.registrations_by("ott")) == 5
    assert len(stocked.registrations_by("kestrel")) == 1


# -- proving ----------------------------------------------------------------

def test_every_registration_can_prove_itself(stocked):
    for entry in stocked.registrations:
        found = stocked.proof_for(entry.file_hash)
        assert stocked.verify(entry.file_hash, found["path"], found["root"])


def test_an_unregistered_file_has_no_proof(stocked):
    assert stocked.proof_for(file_hash(b"never registered")) is None


def test_a_proof_can_be_checked_against_a_root_from_elsewhere(stocked):
    """A proof that can only be checked by asking the registry whether the
    registry is honest proves nothing."""
    entry = stocked.registrations[2]
    found = stocked.proof_for(entry.file_hash)
    independent_root = found["root"]

    stocked.register("kestrel", file_hash(b"later"))

    assert stocked.root() != independent_root
    assert stocked.verify(entry.file_hash, found["path"], independent_root)


def test_a_forged_proof_does_not_verify(stocked):
    entry = stocked.registrations[0]
    found = stocked.proof_for(entry.file_hash)
    tampered = [dict(step) for step in found["path"]]
    tampered[0]["hash"] = "ff" * 32
    assert not stocked.verify(entry.file_hash, tampered, found["root"])


# -- the seal ---------------------------------------------------------------

def test_an_untouched_record_verifies(stocked):
    assert all(stocked.seal_intact(r) for r in stocked.registrations)


def test_editing_any_field_breaks_the_seal(stocked):
    """The signature covers the whole record. Signing a subset leaves the rest
    editable without breaking it, which reads as tamper-evidence and is not."""
    for field, value in (("filename", "renamed.mov"), ("creator", "someone-else"),
                         ("description", "changed"), ("registered_at", "yesterday"),
                         ("leaf_index", 99)):
        entry = stocked.registrations[0]
        original = getattr(entry, field)
        setattr(entry, field, value)
        assert not stocked.seal_intact(entry), field
        setattr(entry, field, original)


def test_the_test_signer_says_it_is_symmetric():
    """A registry that can forge its own checkpoints is asking to be trusted,
    which is what a cryptographic registry exists to avoid."""
    assert HMACSigner.is_asymmetric is False


# -- checkpoints ------------------------------------------------------------

def test_a_checkpoint_signs_the_state(stocked):
    checkpoint = stocked.checkpoint(at="day-5")
    assert checkpoint.leaf_count == 5
    assert checkpoint.root == stocked.root()
    assert stocked.checkpoint_valid(checkpoint)


def test_editing_a_checkpoint_breaks_it(stocked):
    checkpoint = stocked.checkpoint(at="day-5")
    checkpoint.leaf_count = 4
    assert not stocked.checkpoint_valid(checkpoint)


def test_an_empty_registry_cannot_be_check_pointed(chain):
    with pytest.raises(RegistryError, match="no root"):
        chain.checkpoint()


def test_honest_growth_extends_an_earlier_checkpoint(stocked):
    checkpoint = stocked.checkpoint(at="day-5")
    stocked.register("kestrel", file_hash(b"later"))
    assert stocked.extends(checkpoint)


def test_a_rewritten_history_does_not(stocked):
    """The entire value of publishing a root is being able to tell a rewrite
    from honest growth."""
    checkpoint = stocked.checkpoint(at="day-5")
    stocked.registrations[1].file_hash = file_hash(b"swapped")
    assert not stocked.extends(checkpoint)


def test_a_shrunken_registry_does_not(stocked):
    checkpoint = stocked.checkpoint(at="day-5")
    stocked.registrations.pop()
    assert not stocked.extends(checkpoint)


# -- determinism ------------------------------------------------------------

def test_the_same_registrations_give_the_same_root():
    def build():
        chain = Canonchain()
        for i in range(4):
            chain.register("ott", file_hash(f"w{i}".encode()), at="fixed")
        return chain.root()
    assert build() == build()


def test_the_summary_reports_the_registry(stocked):
    summary = stocked.summary()
    assert summary["registrations"] == 5
    assert summary["creators"] == 1
    assert summary["root"] == stocked.root()
