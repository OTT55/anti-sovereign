"""Workspaces, versioned assets, jobs that can fail, and publishing as a snapshot."""

import pytest

from studio_engine import (
    AssetError, JobError, Studio, StudioError, WorkspaceError,
)


class FakeBus:
    def __init__(self):
        self.published = []

    def publish(self, space_id, kind, subject_id, payload, source=""):
        self.published.append({"kind": kind, "subject": subject_id,
                               "payload": payload})
        return len(self.published)

    def kinds(self):
        return [e["kind"] for e in self.published]


@pytest.fixture
def studio():
    return Studio(bus=FakeBus())


@pytest.fixture
def space(studio):
    return studio.create_workspace("ott", "Nightshift")


@pytest.fixture
def project(studio, space):
    return studio.create_project(space.id, "Trailer", by="ott")


@pytest.fixture
def trailer(studio, project):
    return studio.add_asset(project.id, "Trailer cut", by="ott")


# -- membership is offered, not imposed -------------------------------------

def test_the_owner_is_active_from_the_start(space):
    assert space.can("ott", "owner")


def test_an_invitation_grants_nothing_until_accepted(space):
    """Adding somebody to a workspace they never agreed to join puts your files
    in front of a person who cannot be shown to have consented."""
    space.invite("kestrel", "editor", by="ott")
    assert not space.can("kestrel", "viewer")
    assert space.pending_members()[0].handle == "kestrel"


def test_accepting_grants_access(space):
    space.invite("kestrel", "editor", by="ott")
    space.respond("kestrel", accept=True)
    assert space.can("kestrel", "editor")


def test_declining_grants_nothing(space):
    space.invite("kestrel", "editor", by="ott")
    space.respond("kestrel", accept=False)
    assert not space.can("kestrel", "viewer")


def test_an_invitation_can_only_be_answered_once(space):
    space.invite("kestrel", "editor", by="ott")
    space.respond("kestrel", accept=True)
    with pytest.raises(WorkspaceError, match="already active"):
        space.respond("kestrel", accept=False)


def test_only_the_owner_can_invite(space):
    space.invite("kestrel", "editor", by="ott")
    space.respond("kestrel", accept=True)
    with pytest.raises(WorkspaceError, match="Only the workspace owner"):
        space.invite("nova", "editor", by="kestrel")


def test_ownership_is_transferred_not_invited(space):
    with pytest.raises(WorkspaceError, match="two owners"):
        space.invite("kestrel", "owner", by="ott")


def test_the_owner_cannot_be_removed(space):
    with pytest.raises(WorkspaceError, match="nobody who can grant access"):
        space.remove("ott", by="ott")


def test_a_removed_member_loses_access(space):
    space.invite("kestrel", "editor", by="ott")
    space.respond("kestrel", accept=True)
    space.remove("kestrel", by="ott")
    assert not space.can("kestrel", "viewer")


def test_status_is_checked_before_role(space):
    """A pending or removed member can hold the role `owner` and must still be
    refused. Checking the role first is the mistake worth avoiding."""
    space.invite("kestrel", "editor", by="ott")
    member = space.members["kestrel"]
    member.role = "owner"
    assert not member.can("viewer")


def test_a_viewer_cannot_change_anything(studio, space, project):
    space.invite("watcher", "viewer", by="ott")
    space.respond("watcher", accept=True)
    with pytest.raises(WorkspaceError, match="needs to be a editor"):
        studio.add_asset(project.id, "Sneaky", by="watcher")


def test_a_stranger_is_told_they_are_not_a_member(studio, project):
    with pytest.raises(WorkspaceError, match="not a member"):
        studio.add_asset(project.id, "Sneaky", by="nobody")


# -- assets keep their versions ---------------------------------------------

def test_uploading_again_adds_a_version_rather_than_replacing(studio, project, trailer):
    """`final.mov`, `final_v2.mov`, `final_v3_REAL.mov` is what happens when
    software overwrites instead of versioning."""
    studio.upload(project.id, trailer.id, b"cut one", by="ott")
    studio.upload(project.id, trailer.id, b"cut two", by="ott")
    assert len(trailer.versions) == 2
    assert trailer.current.number == 2
    assert trailer.version(1).hash != trailer.version(2).hash


def test_re_uploading_identical_bytes_is_refused(studio, project, trailer):
    """A version that changes nothing is noise in a history whose whole value is
    that every entry means something happened."""
    studio.upload(project.id, trailer.id, b"same", by="ott")
    with pytest.raises(AssetError, match="already at this exact content"):
        studio.upload(project.id, trailer.id, b"same", by="ott")


def test_a_version_can_be_verified_against_its_bytes(studio, project, trailer):
    studio.upload(project.id, trailer.id, b"cut one", by="ott")
    assert trailer.verify(1, b"cut one")
    assert not trailer.verify(1, b"cut one!")


def test_withdrawing_keeps_the_record(studio, project, trailer):
    """Deleting your record does not delete the client's copy — it only removes
    your ability to explain what they are holding."""
    studio.upload(project.id, trailer.id, b"cut one", by="ott")
    studio.upload(project.id, trailer.id, b"cut two", by="ott")
    trailer.withdraw(2, why="wrong grade")
    assert len(trailer.versions) == 2
    assert trailer.current.number == 1
    assert trailer.version(2).note == "wrong grade"


def test_an_asset_with_no_versions_has_no_current(trailer):
    assert trailer.current is None


# -- jobs can fail ----------------------------------------------------------

def test_a_job_walks_its_flow(studio, project):
    job = studio.queue_job(project.id, "render", by="ott")
    assert job.state == "queued"
    studio.advance_job(project.id, job.id)
    assert job.state == "running"
    studio.advance_job(project.id, job.id)
    assert job.succeeded


def test_a_job_can_fail(studio, project):
    """The app documents `failed` in two places and reaches it from nowhere.
    Every job that went wrong either sat in `running` forever or was quietly
    advanced to `done`."""
    job = studio.queue_job(project.id, "render", by="ott")
    studio.advance_job(project.id, job.id)
    studio.fail_job(project.id, job.id, "out of memory")
    assert job.state == "failed"
    assert job.attempt.reason == "out of memory"
    assert "job.failed" in studio.bus.kinds()


def test_a_failure_needs_a_reason(studio, project):
    """"Failed" on its own tells whoever picks this up nothing they can act on,
    and the moment it is optional it is always omitted."""
    job = studio.queue_job(project.id, "render", by="ott")
    with pytest.raises(JobError, match="needs a reason"):
        studio.fail_job(project.id, job.id, "  ")


def test_retrying_keeps_every_attempt(studio, project):
    """A job that failed three times and then worked is a different fact from a
    job that worked, and only one says the pipeline is sick."""
    job = studio.queue_job(project.id, "render", by="ott")
    studio.fail_job(project.id, job.id, "disk full")
    studio.retry_job(project.id, job.id)
    studio.advance_job(project.id, job.id)
    studio.advance_job(project.id, job.id)
    assert job.succeeded
    assert len(job.attempts) == 2
    assert len(job.failures) == 1


def test_only_a_failed_job_can_be_retried(studio, project):
    job = studio.queue_job(project.id, "render", by="ott")
    with pytest.raises(JobError, match="Only a failed job"):
        studio.retry_job(project.id, job.id)


def test_a_finished_job_cannot_be_advanced(studio, project):
    job = studio.queue_job(project.id, "render", by="ott")
    studio.advance_job(project.id, job.id)
    studio.advance_job(project.id, job.id)
    with pytest.raises(JobError, match="already done"):
        studio.advance_job(project.id, job.id)


# -- publishing is a snapshot -----------------------------------------------

def test_publishing_freezes_what_was_published(studio, project, trailer):
    """Ask "what did you publish?" a month later and a status flag answers
    "whatever the project looks like now", which is not an answer."""
    studio.upload(project.id, trailer.id, b"cut one", by="ott")
    studio.upload(project.id, trailer.id, b"cut two", by="ott")
    studio.publish(project.id, by="ott")

    studio.upload(project.id, trailer.id, b"cut three", by="ott")

    assert trailer.current.number == 3
    assert studio.released_version_of(project.id, trailer.id)["version"] == 2


def test_publishing_twice_gives_two_releases(studio, project, trailer):
    studio.upload(project.id, trailer.id, b"one", by="ott")
    studio.publish(project.id, by="ott")
    studio.upload(project.id, trailer.id, b"two", by="ott")
    studio.publish(project.id, by="ott")
    assert len(project.releases) == 2
    assert studio.released_version_of(project.id, trailer.id, 1)["version"] == 1
    assert studio.released_version_of(project.id, trailer.id, 2)["version"] == 2


def test_a_project_with_nothing_in_it_cannot_be_published(studio, project):
    with pytest.raises(StudioError, match="nothing to publish"):
        studio.publish(project.id, by="ott")


def test_a_project_with_a_running_job_cannot_be_published(studio, project, trailer):
    studio.upload(project.id, trailer.id, b"one", by="ott")
    studio.queue_job(project.id, "render", by="ott")
    with pytest.raises(StudioError, match="still running"):
        studio.publish(project.id, by="ott")


def test_a_failed_job_does_not_block_publishing(studio, project, trailer):
    """Failure is an ending. Only unfinished work blocks a release."""
    studio.upload(project.id, trailer.id, b"one", by="ott")
    job = studio.queue_job(project.id, "render", by="ott")
    studio.fail_job(project.id, job.id, "gave up")
    assert studio.publish(project.id, by="ott")


def test_a_viewer_cannot_publish(studio, space, project, trailer):
    studio.upload(project.id, trailer.id, b"one", by="ott")
    space.invite("watcher", "viewer", by="ott")
    space.respond("watcher", accept=True)
    with pytest.raises(WorkspaceError, match="needs to be a editor"):
        studio.publish(project.id, by="watcher")


def test_the_release_exists_before_the_event_is_published(studio, project, trailer):
    """A listener reacting to `project.published` must not arrive before there
    is a release to ask about."""
    studio.upload(project.id, trailer.id, b"one", by="ott")
    seen = {}
    original = studio.bus.publish

    def spy(space_id, kind, subject_id, payload, source=""):
        if kind == "project.published":
            seen["release"] = project.latest_release
        return original(space_id, kind, subject_id, payload, source)

    studio.bus.publish = spy
    studio.publish(project.id, by="ott")
    assert seen["release"] is not None


def test_the_published_event_carries_the_manifest(studio, project, trailer):
    studio.upload(project.id, trailer.id, b"one", by="ott")
    studio.publish(project.id, by="ott")
    payload = studio.bus.published[-1]["payload"]
    assert payload["assets"] == 1
    assert payload["manifest"][0]["hash"] == trailer.current.hash


# -- boundaries -------------------------------------------------------------

def test_the_engine_runs_without_a_bus():
    studio = Studio()
    space = studio.create_workspace("ott", "W")
    project = studio.create_project(space.id, "P", by="ott")
    asset = studio.add_asset(project.id, "A", by="ott")
    studio.upload(project.id, asset.id, b"x", by="ott")
    assert studio.publish(project.id, by="ott").number == 1


def test_unknown_things_are_refused(studio, project):
    with pytest.raises(StudioError, match="Unknown project"):
        studio.add_asset("nope", "A", by="ott")
    with pytest.raises(StudioError, match="Unknown asset"):
        studio.upload(project.id, "nope", b"x", by="ott")
    with pytest.raises(StudioError, match="Unknown job"):
        studio.advance_job(project.id, "nope")


def test_the_engine_imports_nothing_from_a_sibling_application():
    import ast
    import pathlib

    package = pathlib.Path(__file__).resolve().parents[1] / "src" / "studio_engine"
    siblings = ("storyatlas_engine", "framevault_engine", "filmcrew_engine",
                "rightsforge_engine", "creatorstack_engine")
    for module in package.glob("*.py"):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                assert not name.startswith(siblings), f"{module.name} imports {name}"
