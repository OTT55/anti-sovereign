"""OTT Studio Engine — the domain authority for creative execution.

Sits on top of CreativeOS. CreativeOS understands process; Studio understands
that replacing a file is a new version rather than an overwrite, that a job can
fail, and that publishing has to freeze what was published.

Four modules, one idea each:

* `workspace` — membership that is offered rather than imposed, and ordered roles
* `assets`    — slots holding version chains, so "which file is this?" resolves
* `jobs`      — a lifecycle that includes failing, and retrying without erasing
* `studio`    — projects, and publishing as a snapshot rather than a flag

Deterministic and self-contained. It publishes events and holds no reference to
FrameVault or to any other application.

    from studio_engine import Studio

    studio = Studio()
    space = studio.create_workspace("ott", "Nightshift")
    project = studio.create_project(space.id, "Trailer", by="ott")
    trailer = studio.add_asset(project.id, "Trailer cut", by="ott")

    studio.upload(project.id, trailer.id, b"v1 bytes", by="ott")
    studio.upload(project.id, trailer.id, b"v2 bytes", by="ott")
    release = studio.publish(project.id, by="ott")

    studio.upload(project.id, trailer.id, b"v3 bytes", by="ott")
    studio.released_version_of(project.id, trailer.id)   # still v2
"""

from .assets import Asset, AssetError, Version, content_hash
from .jobs import FLOW, TERMINAL, Attempt, Job, JobError
from .studio import Project, Release, Studio, StudioError
from .workspace import MEMBERSHIP, ROLES, Member, Workspace, WorkspaceError, rank

__all__ = [
    # the coordinator
    "Studio", "Project", "Release", "StudioError",
    # workspaces
    "Workspace", "Member", "WorkspaceError", "ROLES", "MEMBERSHIP", "rank",
    # assets
    "Asset", "Version", "AssetError", "content_hash",
    # jobs
    "Job", "Attempt", "JobError", "FLOW", "TERMINAL",
]
