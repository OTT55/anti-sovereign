"""What OTT Studio can tell you a month later.

    python demo.py

The interesting moment is step 5: the project carries on changing after
publication, and the release still means what it meant.
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent / "src"))

for _parent in Path(__file__).resolve().parents:
    if (_parent / "src" / "creativeos_engine").is_dir():
        sys.path.insert(0, str(_parent / "src"))
        break

from studio_engine import (  # noqa: E402
    AssetError, JobError, Studio, StudioError, WorkspaceError,
)


class Bus:
    def __init__(self):
        self.seen = []

    def publish(self, space_id, kind, subject_id, payload, source=""):
        self.seen.append((kind, payload))
        return len(self.seen)


def head(n, title):
    print(f"\n{'─' * 72}\n{n}. {title}\n{'─' * 72}")


bus = Bus()
studio = Studio(bus=bus)

head(1, "A workspace, and membership that is offered rather than imposed")
space = studio.create_workspace("ott", "Nightshift")
space.invite("kestrel", "editor", by="ott")
space.invite("watcher", "viewer", by="ott")
print(f"  {space.describe()}")
print(f"  invited: {[m.handle for m in space.pending_members()]}")
print(f"  can kestrel edit yet? {space.can('kestrel', 'editor')}")
space.respond("kestrel", accept=True)
space.respond("watcher", accept=True)
print(f"  after accepting:      {space.can('kestrel', 'editor')}")
print("\n  Adding somebody to a workspace they never agreed to join puts your")
print("  files in front of a person who cannot be shown to have consented.")

head(2, "Assets keep their versions instead of being overwritten")
project = studio.create_project(space.id, "Trailer", by="ott")
trailer = studio.add_asset(project.id, "Trailer cut", by="ott")
for note, data in (("first assembly", b"cut one"),
                   ("tighter open", b"cut two")):
    version = studio.upload(project.id, trailer.id, data, filename="trailer.mov",
                            by="ott", note=note)
    print(f"  {version.label}  {version.hash[:16]}…  {note}")

try:
    studio.upload(project.id, trailer.id, b"cut two", by="kestrel")
except AssetError as error:
    print(f"  re-uploading identical bytes — refused: {error}")

print("\n  final.mov, final_v2.mov, final_v3_REAL.mov is what happens when")
print("  software overwrites instead of versioning.")

head(3, "A job can fail — and the app it replaces has no way to say so")
job = studio.queue_job(project.id, "render", by="ott")
studio.advance_job(project.id, job.id)
studio.fail_job(project.id, job.id, "ran out of memory on the 4K pass")
print(f"  {job.describe()}  →  {job.attempt.reason}")
try:
    studio.fail_job(project.id, job.id, "")
except JobError as error:
    print(f"  failing without a reason — refused: {error}")

studio.retry_job(project.id, job.id)
studio.advance_job(project.id, job.id)
studio.advance_job(project.id, job.id)
print(f"  after retry: {job.describe()}, {len(job.failures)} failure kept")
print("\n  A job that failed once and then worked is a different fact from a")
print("  job that worked, and only one says the pipeline is sick.")

head(4, "Publishing freezes what was published")
release = studio.publish(project.id, by="ott")
print(f"  {release.describe()}")
for item in release.manifest:
    print(f"    {item['label']}  v{item['version']}  {item['hash'][:16]}…")

head(5, "The project moves on. The release does not.")
studio.upload(project.id, trailer.id, b"cut three", by="kestrel",
              note="colour pass")
released = studio.released_version_of(project.id, trailer.id)
print(f"  the asset is now at v{trailer.current.number}")
print(f"  the release still points at v{released['version']}")
print("\n  Ask \"what did you publish?\" a month later and a status flag answers")
print("  \"whatever the project looks like now\", which is not an answer.")

head(6, "What publishing refuses")
empty = studio.create_project(space.id, "Nothing yet", by="ott")
try:
    studio.publish(empty.id, by="ott")
except StudioError as error:
    print(f"  an empty project — refused: {error}")
try:
    studio.publish(project.id, by="watcher")
except WorkspaceError as error:
    print(f"  a viewer publishing — refused: {error}")

head(7, "What was published to the ecosystem")
for kind, payload in bus.seen:
    if kind in ("project.published", "job.failed"):
        detail = payload.get("reason") or f"{payload.get('assets')} asset(s)"
        print(f"  {kind:20} {detail}")
print("\n  Events only. Studio holds no reference to FrameVault.")

print(f"\n{'─' * 72}")
print(f"{studio.summary()}")
print("Every version still addressable, every attempt still recorded, and the")
print("release still means what it meant.")
print(f"{'─' * 72}\n")
