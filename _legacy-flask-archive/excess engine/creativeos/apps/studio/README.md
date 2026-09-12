# OTT Studio Engine

The domain authority for **creative execution**, sitting on top of CreativeOS.

```bash
python demo.py
python -m pytest -q     # 34 tests
```

CreativeOS understands process. Studio understands that replacing a file is a
new version rather than an overwrite, that a job can fail, and that publishing
has to freeze what was published.

## Publishing is a snapshot, not a flag

The app publishes by setting `status='published'` on a row. The project then
carries on changing — assets replaced, jobs run — so the published thing is a
moving target. Ask *"what did you publish?"* a month later and the honest answer
is "whatever the project looks like now", which is not an answer.

A **Release** captures a manifest: every asset, the exact version, its content
hash, at that moment.

```python
studio.upload(project.id, trailer.id, b"cut two", by="ott")
studio.publish(project.id, by="ott")
studio.upload(project.id, trailer.id, b"cut three", by="ott")

trailer.current.number                                  # 3
studio.released_version_of(project.id, trailer.id)      # v2
```

Publishing twice gives two releases — a version history rather than a lost first
answer. Same instinct as RightsForge recording a grant instead of a status and
CreatorStack computing a phase instead of storing one: **a flag cannot hold the
fact you will need later.**

## Assets keep their versions

`final.mov`, `final_v2.mov`, `final_v3_REAL.mov` is what happens when software
overwrites instead of versioning. The app's `studio_assets` table has one row
per asset and no version column — `version` appears once in 654 lines.

Here an asset is a **slot** holding an ordered chain. Uploading adds; it never
replaces. Re-uploading identical bytes is refused, because a version that
changes nothing is noise in a history whose whole value is that every entry
means something happened.

Withdrawing marks and does not delete. Deleting your record does not delete the
client's copy — it only removes your ability to explain what they are holding.

## A job can fail

The app's schema documents four states in two places:

```
status TEXT DEFAULT 'queued',   -- queued | running | done | failed
```

and its flow is `["queued", "running", "done"]`. Searching the whole file,
`failed` appears **only in those two comments**. A job can never fail. Anything
that went wrong sat in `running` forever or was quietly advanced to `done` —
worse than not modelling failure at all, because the schema promises a
distinction the API cannot make.

```
queued ──▶ running ──▶ done
               └─────▶ failed ──▶ (retry) ──▶ queued
```

A failure needs a reason; the moment it is optional it is always omitted.
Retrying starts a **new attempt** rather than resurrecting the old one, so a job
that failed three times and then worked stays distinguishable from a job that
worked — and only one of those says the pipeline is sick.

## Membership is offered, not imposed

`invite()` creates a **pending** membership that grants nothing until accepted.
Adding somebody to a workspace they never agreed to join puts your files in
front of a person who cannot be shown to have consented.

Roles are ordered — `viewer < editor < owner` — and every check is "at least
X", never set membership, so a new role cannot create a gap where one permission
table was forgotten. Status is checked **before** role: a pending or removed
member can hold `owner` and must still be refused.

**This belongs in the platform.** FilmCrew has the same flow for collaborators
and wrote its own; a third application will write a third. It is noted in
`PHASE-12-ECOSYSTEM.md` — the same journey `money` took out of RightsForge.

## Boundaries

Publishes `workspace.created`, `project.created`, `asset.versioned`,
`job.queued`, `job.done`, `job.failed` and `project.published`, and holds no
reference to FrameVault. A test parses the engine's imports and fails if it
reaches sideways.

The manifest is captured **before** `project.published` goes out, tested with a
spy — a listener that reacts by asking what was released cannot arrive before
the answer exists.

## Honest limitations

- **No bytes are stored.** The engine records hashes, versions and manifests;
  the file lives in the platform's storage engine or wherever the app puts it.
- **Time is a plain comparable** and never arithmetic.
- **No AI backend**, exactly as the app is honest about: a job is a real state
  machine advanced by hand. The orchestration is real; the work behind it is the
  application's to supply.
- **In-memory.** Persistence is the application's job.
