# Canonchain Engine

Proving **who held these exact bytes first** — and refusing to claim more.

```bash
python demo.py
python -m pytest -q     # 52 tests
```

## The tree was the product, and the tree was broken

Canonchain's whole claim is that one 64-hex root fingerprints the entire
registry, so anyone can check an entry is really in it and the operator cannot
silently drop or fake one. Two flaws in `app/registry.py` break that. Both were
verified against the running code before a line of this engine was written, and
`demo.py` runs the app's algorithm alongside this one so the difference is
visible rather than asserted.

### 1. Odd nodes are duplicated — CVE-2012-2459

```python
_pair(level[i], level[i + 1] if i + 1 < len(level) else level[i])
```

An odd last node is paired **with itself**, so two different registries produce
the same root:

```
root([a, b, c])    = f372961e0178fea099eb05057b8b6a36
root([a, b, c, c]) = f372961e0178fea099eb05057b8b6a36   ← identical
```

A root two registries can share does not commit to a registry. This is the flaw
that hit Bitcoin in 2012, and it is the same line of code.

### 2. An internal node can pose as a registered work

Leaves and internal nodes are hashed identically, so a node value can be
presented as a registered file and a proof built for it verifies — **an
inclusion proof for something nobody ever registered.** For a rights registry
that is the worst available failure, because the proof *is* the product.

### The fix

RFC 6962 (Certificate Transparency) domain separation:

```
leaf hash     = SHA256(0x00 ‖ value)
internal node = SHA256(0x01 ‖ left ‖ right)
```

The prefixes make the two hash functions disjoint, so flaw 2 disappears by
construction rather than by a check somebody has to remember. Odd nodes are
**promoted** rather than duplicated, so the tree depends on the exact leaf count
and flaw 1 disappears too.

Neither is clever. They are what a Merkle tree has to do to mean what everyone
assumes it means.

## What it will and will not say

| Question | Answer |
|---|---|
| Was this exact file registered, and when? | yes, with a proof |
| Who registered it first? | yes — the earliest leaf, by position |
| Did they create it? | **no** |

There is no `owner_of()`. `first_claim()` returns the earliest registration and
is named for what it is: registering someone else's file records that you held
it. An engine that upgrades a timestamp into authorship is making a legal claim
out of an ordering fact.

## Append-only, and checkable

A checkpoint signs `(leaf_count, root)`. `extends()` confirms the registry today
genuinely continues an earlier checkpoint rather than having quietly rewritten
it — the question a published root invites and which the app has no way to
answer. Without it, a rewrite and honest growth look identical from outside.

Old proofs keep verifying forever, against the root of the day they were issued.
`verify()` takes the root as an argument precisely so a third party can check
against one they obtained elsewhere: a proof that can only be checked by asking
the registry whether the registry is honest proves nothing.

## Honest limitations

- **`HMACSigner` is symmetric and test-only**, and says so with
  `is_asymmetric = False`. A registry that can forge its own checkpoints is
  asking to be trusted, which is exactly what a cryptographic registry exists to
  avoid. Real deployments sign with a key the registry does not hold.
- **Nothing anchors time.** A checkpoint proves an order, not a date. Real
  anchoring means publishing the root somewhere the operator does not control.
- **First registration is not authorship**, as above. It is a strong signal in a
  dispute and it is not proof.
- **In-memory.** Persistence is the application's job.
