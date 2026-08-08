# 0001 — What Sovereign Edit is for, and the chain

**Date:** 2026-07-22
**Status:** Accepted

## Context

A finished film exists as a dozen near-identical files — `final.mov`,
`final_v2.mov`, `final_v3_REAL.mov` — spread across drives, festival portals, and
collaborators' inboxes. Months later nobody can reliably answer *which one is the
approved master*, *who did what*, or *whether the copy a festival holds is the cut
that was signed off*. Right now this is managed by memory and filenames, and it
fails constantly.

## Decision

**Sovereign Edit records a work's production lineage as a hash-linked chain, and
answers one question above all others: given this file, what is it?**

1. **Each production step is a block.** Capture, edit, colour, sound, master,
   release — each records who did it, what tool, and the SHA-256 of the artefact
   it produced.
2. **Blocks are chained.** `block_hash = SHA-256(prev_hash + step fields)`. Change
   any past step and its hash changes, breaking every link after it. Verification
   reports *exactly which step* the lineage stops being trustworthy at.
3. **Files are fingerprinted in the browser and never uploaded.** Masters are tens
   of gigabytes; uploading them would make the tool unusable and turn us into a
   storage liability. We only ever need the hash.
4. **The headline feature is `/identify`.** Drop a file, get one of four answers:
   **APPROVED MASTER**, **NOT THE MASTER** (with a pointer to which step *is*),
   **IN LINEAGE** (no master designated yet), or **NOT IN THE ARCHIVE**.

## Why

- **The chain, not a database table, is the point.** A plain log can be edited by
  anyone with database access, so it proves nothing. Chaining makes silent
  rewriting detectable, which is what makes the certificate worth anything.
- **Reporting *where* the chain breaks beats a yes/no.** If step 2 was altered,
  steps 0–1 are still trustworthy. Saying so is more useful and more honest than
  condemning the whole work.
- **`/identify` is the product.** Everything else is bookkeeping in service of the
  moment you're about to send a file somewhere and need to know what it is.

## Trade-off

- **Sovereign Edit proves a file's *place in a recorded history*, not that the
  history is true.** If someone logs a step that never happened, the chain
  faithfully records a lie. It guarantees the record hasn't been *altered since*,
  not that it was honest when written. Tying steps to signed identities (the
  Nullform/Veridact direction) is how that would tighten later.
- **Hash-only means we can't show you the file.** You get identity and integrity,
  not preview or storage. That's the right trade for 40GB masters, but it does
  mean Sovereign Edit is a ledger, not an asset manager.
