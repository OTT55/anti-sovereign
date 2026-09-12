"""Projects, and what publishing actually means.

## Publishing is a snapshot, not a flag

The app publishes by setting `status='published'` on a row. The project then
keeps changing — assets get replaced, jobs run — and the published thing is a
moving target. Ask *"what did you publish?"* a month later and the honest answer
is "whatever the project looks like now", which is not an answer.

So a **Release** captures a manifest: every asset, the exact version, and its
content hash, at the moment of publication. Afterwards:

* the project can carry on changing without rewriting history,
* "what did you publish" resolves to specific bytes,
* and publishing twice produces two releases, which is a version history rather
  than a lost first answer.

This is the same instinct as RightsForge recording a grant instead of a status
and CreatorStack computing a phase instead of storing one: **a flag cannot hold
the fact you will need later.**

## Publishing is gated on the work being finished

A project with a running job is not finished, and a project with no assets has
nothing to publish. Both are refused, because a release that points at an empty
manifest is a claim with nothing behind it.

Like every other application engine here, this publishes events and holds no
reference to FrameVault.
"""

from .assets import Asset, AssetError
from .jobs import Job, JobError
from .workspace import Workspace, WorkspaceError


class StudioError(Exception):
    """Raised when a studio operation cannot proceed."""


class Release:
    """What a project was at the moment it was published."""

    __slots__ = ("id", "project_id", "number", "manifest", "by", "at", "note")

    def __init__(self, id, project_id, number, manifest, by=None, at=None, note=""):
        self.id = id
        self.project_id = project_id
        self.number = number
        #: `[{"asset", "label", "version", "hash"}]` — frozen at publication.
        self.manifest = manifest
        self.by = by
        self.at = at
        self.note = note

    def contains(self, digest):
        return any(item["hash"] == digest for item in self.manifest)

    def describe(self):
        return (f"release {self.number}: {len(self.manifest)} asset(s), "
                f"published by {self.by}")

    def __repr__(self):
        return f"<Release {self.describe()}>"


class Project:
    """A body of work inside a workspace."""

    __slots__ = ("id", "workspace_id", "name", "assets", "jobs", "releases",
                 "created_at")

    def __init__(self, id, workspace_id, name, created_at=None):
        if not (name or "").strip():
            raise StudioError("A project needs a name.")
        self.id = id
        self.workspace_id = workspace_id
        self.name = name
        self.assets = {}
        self.jobs = {}
        self.releases = []
        self.created_at = created_at

    @property
    def is_published(self):
        return bool(self.releases)

    @property
    def latest_release(self):
        return self.releases[-1] if self.releases else None

    def describe(self):
        state = (f"published ×{len(self.releases)}" if self.releases
                 else "unpublished")
        return f"{self.name} — {len(self.assets)} asset(s) — {state}"

    def __repr__(self):
        return f"<Project {self.describe()}>"


class Studio:
    """Workspaces, projects, assets, jobs and releases."""

    def __init__(self, bus=None, space_id="", source="studio"):
        self.bus = bus
        self.space_id = space_id
        self.source = source
        self.workspaces = {}
        self.projects = {}
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

    # -- workspaces --------------------------------------------------------

    def create_workspace(self, owner, name, at=None):
        workspace = Workspace(self._id("W"), owner, name, created_at=at)
        self.workspaces[workspace.id] = workspace
        self._publish("workspace.created", workspace.id,
                      {"name": name, "owner": owner})
        return workspace

    def workspace(self, workspace_id):
        workspace = self.workspaces.get(workspace_id)
        if workspace is None:
            raise StudioError(f"Unknown workspace '{workspace_id}'.")
        return workspace

    # -- projects ----------------------------------------------------------

    def create_project(self, workspace_id, name, by, at=None):
        workspace = self.workspace(workspace_id)
        workspace.require(by, "editor", "create a project")
        project = Project(self._id("P"), workspace_id, name, created_at=at)
        self.projects[project.id] = project
        self._publish("project.created", project.id,
                      {"name": name, "workspace": workspace_id, "by": by})
        return project

    def project(self, project_id):
        project = self.projects.get(project_id)
        if project is None:
            raise StudioError(f"Unknown project '{project_id}'.")
        return project

    # -- assets ------------------------------------------------------------

    def add_asset(self, project_id, label, kind="video", by=None):
        project = self.project(project_id)
        self._require(project, by, "editor", "add an asset")
        asset = Asset(self._id("A"), project_id, label, kind)
        project.assets[asset.id] = asset
        return asset

    def upload(self, project_id, asset_id, data, filename="", media_type="",
               by=None, at=None, note=""):
        """Add a version to an asset. Never overwrites."""
        project = self.project(project_id)
        self._require(project, by, "editor", "upload")
        asset = project.assets.get(asset_id)
        if asset is None:
            raise StudioError(f"Unknown asset '{asset_id}'.")
        version = asset.add(data, filename, media_type, by=by, at=at, note=note)
        self._publish("asset.versioned", asset_id,
                      {"project": project_id, "label": asset.label,
                       "version": version.number, "hash": version.hash})
        return version

    # -- jobs --------------------------------------------------------------

    def queue_job(self, project_id, kind, by=None, at=None):
        project = self.project(project_id)
        self._require(project, by, "editor", "queue a job")
        job = Job(self._id("J"), project_id, kind, created_at=at)
        project.jobs[job.id] = job
        self._publish("job.queued", job.id, {"project": project_id, "kind": kind})
        return job

    def advance_job(self, project_id, job_id, at=None, result=None):
        job = self._job(project_id, job_id)
        job.advance(at=at, result=result)
        if job.succeeded:
            self._publish("job.done", job.id, {"project": project_id,
                                               "kind": job.kind})
        return job

    def fail_job(self, project_id, job_id, reason, at=None):
        job = self._job(project_id, job_id)
        job.fail(reason, at=at)
        self._publish("job.failed", job.id,
                      {"project": project_id, "kind": job.kind, "reason": reason,
                       "attempt": job.attempt.number})
        return job

    def retry_job(self, project_id, job_id, at=None):
        job = self._job(project_id, job_id)
        job.retry(at=at)
        self._publish("job.queued", job.id,
                      {"project": project_id, "kind": job.kind,
                       "attempt": job.attempt.number})
        return job

    def _job(self, project_id, job_id):
        project = self.project(project_id)
        job = project.jobs.get(job_id)
        if job is None:
            raise StudioError(f"Unknown job '{job_id}'.")
        return job

    # -- publishing --------------------------------------------------------

    def publish(self, project_id, by, at=None, note=""):
        """Freeze what the project is right now, and announce it.

        The manifest is captured **before** the event is published, so a
        listener that reacts by asking what was released cannot arrive before
        the answer exists — the same ordering RightsForge uses for grants and
        CreatorStack for awards.
        """
        project = self.project(project_id)
        self._require(project, by, "editor", "publish")

        unfinished = [j for j in project.jobs.values() if not j.is_finished]
        if unfinished:
            raise StudioError(
                f"'{project.name}' has {len(unfinished)} job(s) still running. "
                "Publishing now would release work that is not finished.")

        manifest = []
        for asset in project.assets.values():
            current = asset.current
            if current is None:
                continue
            manifest.append({
                "asset": asset.id,
                "label": asset.label,
                "kind": asset.kind,
                "version": current.number,
                "hash": current.hash,
            })
        if not manifest:
            raise StudioError(
                f"'{project.name}' has nothing to publish — a release pointing "
                "at an empty manifest is a claim with nothing behind it.")

        release = Release(self._id("R"), project_id, len(project.releases) + 1,
                          manifest, by=by, at=at, note=note)
        project.releases.append(release)

        self._publish("project.published", project_id, {
            "name": project.name,
            "workspace": project.workspace_id,
            "by": by,
            "release": release.number,
            "assets": len(manifest),
            "manifest": manifest,
        })
        return release

    def released_version_of(self, project_id, asset_id, release_number=None):
        """Which version of an asset a given release points at.

        The question a status flag cannot answer: the asset has moved on since,
        and the release still means what it meant.
        """
        project = self.project(project_id)
        if not project.releases:
            return None
        release = (project.releases[release_number - 1] if release_number
                   else project.latest_release)
        for item in release.manifest:
            if item["asset"] == asset_id:
                return item
        return None

    # -- helpers -----------------------------------------------------------

    def _require(self, project, who, role, what):
        if who is None:
            return True
        self.workspace(project.workspace_id).require(who, role, what)
        return True

    def summary(self):
        jobs = [j for p in self.projects.values() for j in p.jobs.values()]
        return {
            "workspaces": len(self.workspaces),
            "projects": len(self.projects),
            "assets": sum(len(p.assets) for p in self.projects.values()),
            "versions": sum(len(a.versions) for p in self.projects.values()
                            for a in p.assets.values()),
            "jobs": len(jobs),
            "failed_attempts": sum(len(j.failures) for j in jobs),
            "releases": sum(len(p.releases) for p in self.projects.values()),
        }


__all__ = ["Studio", "Project", "Release", "StudioError"]
