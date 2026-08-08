"""Phase 10 — the Platform Engine.

Accounts, organizations, membership, roles and permissions — the job currently
trapped inside FrameVault.
"""

import pytest

from creativeos_engine.platform import PlatformEngine, PlatformError


@pytest.fixture
def platform(graph):
    return PlatformEngine(graph.store.conn, bus=graph.bus)


@pytest.fixture
def ott(platform):
    return platform.create_account("ott", "OTT")


# -- accounts --------------------------------------------------------------

def test_an_account_is_created_and_found_by_handle(platform):
    account = platform.create_account("@OTT", "OTT")
    assert account.handle == "ott"          # normalised
    assert platform.account_by_handle("ott").id == account.id


def test_a_handle_cannot_be_taken_twice(platform, ott):
    with pytest.raises(PlatformError):
        platform.create_account("ott")


def test_an_account_can_point_at_a_graph_entity(graph, platform, space):
    entity = graph.create_entity(space.id, "character", "OTT")
    account = platform.create_account("ott2", entity_id=entity.id)
    assert account.entity_id == entity.id


# -- authentication --------------------------------------------------------

def test_authentication_delegates_to_a_verifier(platform, ott):
    """The platform never sees a credential."""
    assert platform.authenticate("ott", lambda a: True).id == ott.id
    assert platform.authenticate("ott", lambda a: False) is None


def test_a_verifier_that_throws_authenticates_nobody(platform, ott):
    def explodes(account):
        raise RuntimeError("credential store down")

    assert platform.authenticate("ott", explodes) is None


def test_an_unknown_handle_authenticates_to_nothing(platform):
    assert platform.authenticate("nobody", lambda a: True) is None


# -- organizations and membership ------------------------------------------

def test_creating_an_organization_makes_its_creator_owner(platform, ott):
    org = platform.create_organization("Sundered Coast", owner=ott.id)
    assert platform.role_of(org.id, ott.id) == "owner"


def test_a_slug_cannot_be_taken_twice(platform, ott):
    platform.create_organization("Studio", owner=ott.id)
    with pytest.raises(PlatformError):
        platform.create_organization("Studio")


def test_members_can_be_added_and_listed(platform, ott):
    org = platform.create_organization("Studio", owner=ott.id)
    mara = platform.create_account("mara")
    platform.add_member(org.id, mara.id, role="editor")
    assert dict(platform.members(org.id))[mara.id] == "editor"


def test_an_unknown_role_is_rejected(platform, ott):
    org = platform.create_organization("Studio", owner=ott.id)
    with pytest.raises(PlatformError):
        platform.add_member(org.id, ott.id, role="wizard")


def test_the_last_owner_cannot_be_removed(platform, ott):
    """An organization nobody can administer is unrecoverable."""
    org = platform.create_organization("Studio", owner=ott.id)
    with pytest.raises(PlatformError) as e:
        platform.remove_member(org.id, ott.id)
    assert "last owner" in str(e.value)


def test_an_owner_can_be_removed_once_another_exists(platform, ott):
    org = platform.create_organization("Studio", owner=ott.id)
    mara = platform.create_account("mara")
    platform.add_member(org.id, mara.id, role="owner")
    platform.remove_member(org.id, ott.id)
    assert platform.role_of(org.id, ott.id) is None


def test_organizations_are_listed_per_account(platform, ott):
    platform.create_organization("A", owner=ott.id)
    platform.create_organization("B", owner=ott.id)
    assert {o.name for o in platform.organizations_for(ott.id)} == {"A", "B"}


# -- permissions -----------------------------------------------------------

def test_a_viewer_can_read_but_not_delete(platform, ott):
    org = platform.create_organization("Studio", owner=ott.id)
    viewer = platform.create_account("viewer")
    platform.add_member(org.id, viewer.id, role="viewer")

    assert platform.can(org.id, viewer.id, "read")
    assert not platform.can(org.id, viewer.id, "delete")


def test_an_owner_can_do_everything_an_admin_can(platform, ott):
    org = platform.create_organization("Studio", owner=ott.id)
    assert platform.can(org.id, ott.id, "delete")
    assert platform.can(org.id, ott.id, "billing")


def test_a_non_member_can_do_nothing(platform, ott):
    org = platform.create_organization("Studio", owner=ott.id)
    stranger = platform.create_account("stranger")
    assert not platform.can(org.id, stranger.id, "read")


def test_seniority_is_comparable_not_exact(platform, ott):
    org = platform.create_organization("Studio", owner=ott.id)
    editor = platform.create_account("editor")
    platform.add_member(org.id, editor.id, role="editor")

    assert platform.has_at_least(org.id, editor.id, "contributor")
    assert not platform.has_at_least(org.id, editor.id, "admin")


def test_require_raises_with_a_useful_message(platform, ott):
    org = platform.create_organization("Studio", owner=ott.id)
    viewer = platform.create_account("viewer")
    platform.add_member(org.id, viewer.id, role="viewer")

    with pytest.raises(PlatformError) as e:
        platform.require(org.id, viewer.id, "delete")
    assert "viewer" in str(e.value)


# -- spaces -------------------------------------------------------------

def test_an_unattached_space_is_unrestricted(platform, ott, space):
    assert platform.can_access_space(ott.id, space.id)


def test_attaching_a_space_restricts_it_to_members(platform, ott, space):
    org = platform.create_organization("Studio", owner=ott.id)
    platform.attach_space(org.id, space.id)
    stranger = platform.create_account("stranger")

    assert platform.can_access_space(ott.id, space.id)
    assert not platform.can_access_space(stranger.id, space.id)


def test_write_access_is_distinct_from_read(platform, ott, space):
    org = platform.create_organization("Studio", owner=ott.id)
    platform.attach_space(org.id, space.id)
    viewer = platform.create_account("viewer")
    platform.add_member(org.id, viewer.id, role="viewer")

    assert platform.can_access_space(viewer.id, space.id, "read")
    assert not platform.can_access_space(viewer.id, space.id, "update")


# -- notifications ---------------------------------------------------------

def test_notifications_ride_the_event_bus(graph, platform, ott):
    """Not a second mechanism — the Event Engine already does this."""
    seen = []
    graph.bus.subscribe("notification.sent", seen.append)
    platform.notify(ott.id, "Your draft was reviewed.")

    assert len(seen) == 1
    assert seen[0].payload["message"] == "Your draft was reviewed."


def test_account_creation_emits_an_event(graph, platform):
    seen = []
    graph.bus.subscribe("account.created", seen.append)
    platform.create_account("newcomer")
    assert len(seen) == 1
