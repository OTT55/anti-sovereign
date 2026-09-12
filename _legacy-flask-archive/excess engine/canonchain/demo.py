"""What Canonchain can prove, and the two flaws it fixes.

    python demo.py

Steps 1 and 2 are run against the *app's* algorithm as well as this one, so the
difference is visible rather than asserted.
"""

import hashlib
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent / "src"))

from canonchain_engine import (  # noqa: E402
    Canonchain, DuplicateRegistration, RegistryError, file_hash, leaf_hash,
    node_hash, root, verify,
)


# The app's tree, reproduced here so the comparison is real rather than claimed.
def _app_pair(left, right):
    return hashlib.sha256((left + right).encode()).hexdigest()


def app_root(leaves):
    if not leaves:
        return None
    level = list(leaves)
    while len(level) > 1:
        level = [_app_pair(level[i], level[i + 1] if i + 1 < len(level) else level[i])
                 for i in range(0, len(level), 2)]
    return level[0]


def head(n, title):
    print(f"\n{'─' * 72}\n{n}. {title}\n{'─' * 72}")


A, B, C = ("aa" * 32, "bb" * 32, "cc" * 32)

head(1, "Flaw one: a duplicated last leaf forges the same root")
print(f"  app   root([a,b,c])   = {app_root([A, B, C])[:32]}")
print(f"  app   root([a,b,c,c]) = {app_root([A, B, C, C])[:32]}")
print(f"  identical? {app_root([A, B, C]) == app_root([A, B, C, C])}")
print()
print(f"  engine root([a,b,c])   = {root([A, B, C])[:32]}")
print(f"  engine root([a,b,c,c]) = {root([A, B, C, C])[:32]}")
print(f"  identical? {root([A, B, C]) == root([A, B, C, C])}")
print("\n  A root two different registries can share does not commit to a")
print("  registry. This is CVE-2012-2459, and it is the same line of code.")

head(2, "Flaw two: an internal node poses as a registered work")
app_tree = app_root([A, B, C])
app_internal = _app_pair(A, B)
computed = _app_pair(app_internal, _app_pair(C, C))
print(f"  app: is H(a+b) 'in' the registry? {computed == app_tree}")
print("       — an inclusion proof for something nobody registered.")
print()
engine_tree = root([A, B, C])
engine_internal = node_hash(leaf_hash(A), leaf_hash(B))
print(f"  engine: same attempt accepted? "
      f"{verify(engine_internal, [{'position': 'right', 'hash': leaf_hash(C)}], engine_tree)}")
print("\n  Leaves are hashed with 0x00 and nodes with 0x01, so the two hash")
print("  functions are disjoint and no node can ever equal a leaf.")

head(3, "Registering a work — the registry never sees the file")
chain = Canonchain()
works = [("ott", b"Nightshift final cut", "nightshift.mov"),
         ("ott", b"Nightshift score", "score.wav"),
         ("kestrel", b"Harbour teaser", "harbour.mov")]
for creator, data, name in works:
    entry = chain.register(creator, file_hash(data), filename=name,
                           at="2026-08-03")
    print(f"  {entry.registry_id}  {entry.creator:8} {name:16} "
          f"leaf {entry.leaf_index}  {entry.file_hash[:16]}…")
print("\n  A hash discloses nothing about the content, which is what makes it")
print("  safe to register an unreleased work.")

head(4, "Proving it — checkable by anyone, against a root from anywhere")
entry = chain.registrations[1]
found = chain.proof_for(entry.file_hash)
print(f"  proving {entry.filename} at leaf {found['leaf_index']}")
for step in found["path"]:
    print(f"    fold {step['position']:5} {step['hash'][:32]}…")
print(f"  → root {found['root'][:32]}…")
print(f"  verifies: {chain.verify(entry.file_hash, found['path'], found['root'])}")

head(5, "The registry grows. The old proof still verifies.")
checkpoint = chain.checkpoint(at="2026-08-03")
print(f"  checkpoint: {checkpoint.describe()}  signed: "
      f"{chain.checkpoint_valid(checkpoint)}")
chain.register("nova", file_hash(b"a later work"), filename="later.mov")
print(f"  after one more registration, root is {chain.root()[:32]}…")
print(f"  old proof still verifies: "
      f"{chain.verify(entry.file_hash, found['path'], found['root'])}")
print(f"  and today genuinely extends that checkpoint: {chain.extends(checkpoint)}")

head(6, "What it refuses")
try:
    chain.register("someone-else", entry.file_hash)
except DuplicateRegistration as error:
    print(f"  the same bytes twice — refused: {error}")
try:
    chain.register("ott", "not-a-hash")
except RegistryError as error:
    print(f"  a value that is not a hash — refused: {error}")

original = chain.registrations[0].filename
chain.registrations[0].filename = "renamed.mov"
print(f"  a record edited after signing — seal intact? "
      f"{chain.seal_intact(chain.registrations[0])}")
chain.registrations[0].filename = original

head(7, "What it will NOT claim")
print("  first_claim() returns the earliest registration — an ordering fact.")
print("  There is no owner_of(). Registering somebody else's file records that")
print("  you held it, and turning a timestamp into authorship is a legal claim")
print("  the registry has no basis for.")

print(f"\n{'─' * 72}")
print(f"{ {k: v for k, v in chain.summary().items() if k != 'root'} }")
print("One root, and it means exactly one registry.")
print(f"{'─' * 72}\n")
