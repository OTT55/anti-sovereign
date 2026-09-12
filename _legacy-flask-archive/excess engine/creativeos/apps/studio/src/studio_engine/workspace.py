"""Workspaces, membership, and who may do what.

OTT Studio understands **work**; CreativeOS understands process. A workspace is
where work happens and the roles decide who can change it.

## Membership is offered, not imposed

`invite()` creates a **pending** membership. Nothing about that person's access
changes until they accept. The app already gets this right — it has an
`invite/respond` flow and a `status` column — and it is worth stating why,
because the obvious shortcut is to add somebody immediately and call it an
invitation. Adding a person to a workspace they never agreed to join puts your
files in front of somebody who did not ask for them and cannot be shown to have
consented.

**This belongs in the platform, not here.** FilmCrew has the same flow for
project collaborators and wrote its own; a third application will write a third.
It lives in Studio for now because that is where it is needed today, and it is
noted in `PHASE-12-ECOSYSTEM.md` as platform work — the same journey `money`
took out of RightsForge once CreatorStack needed it.

## Roles are ordered, and permission is a comparison

`viewer < editor < owner`. Every check is "is this role at least X", never a set
membership test, because an ordered ladder cannot develop the gap where a new
role is added and one permission table is forgotten.
"""

#: Ordered, weakest first. Position *is* the permission level.
ROLES = ("viewer", "editor", "owner")

#: Membership states. A pending member has no access at all.
MEMBERSHIP = ("pending", "active", "declined", "removed")


class WorkspaceError(Exception):
    """Raised when a workspace rule would be broken."""


def rank(role):
    if role not in ROLES:
        raise WorkspaceError(f"Unknown role '{role}'. Known: {', '.join(ROLES)}.")
    return ROLES.index(role)


class Member:
    """One person's standing in a workspace."""

    __slots__ = ("handle", "role", "status", "invited_by")

    def __init__(self, handle, role="editor", status="pending", invited_by=None):
        if status not in MEMBERSHIP:
            raise WorkspaceError(f"Unknown membership status '{status}'.")
        rank(role)
        self.handle = handle
        self.role = role
        self.status = status
        self.invited_by = invited_by

    @property
    def has_access(self):
        return self.status == "active"

    def can(self, needed):
        """Access is status **and** role, in that order.

        Checking the role first is the mistake worth avoiding: a pending or
        removed member can hold the role `owner` and must still be refused.
        """
        return self.has_access and rank(self.role) >= rank(needed)

    def describe(self):
        return f"{self.handle} ({self.role}, {self.status})"

    def __repr__(self):
        return f"<Member {self.describe()}>"


class Workspace:
    """Where work happens."""

    __slots__ = ("id", "owner", "name", "members", "created_at")

    def __init__(self, id, owner, name, created_at=None):
        if not (owner or "").strip():
            raise WorkspaceError("A workspace needs an owner.")
        if not (name or "").strip():
            raise WorkspaceError("A workspace needs a name.")
        self.id = id
        self.owner = owner
        self.name = name
        self.created_at = created_at
        # The owner is active from the start: they created it, so there is
        # nothing for them to accept.
        self.members = {owner: Member(owner, "owner", "active")}

    # -- membership --------------------------------------------------------

    def invite(self, handle, role="editor", by=None):
        """Offer membership. Grants nothing until accepted."""
        if not (handle or "").strip():
            raise WorkspaceError("An invitation needs somebody to invite.")
        if by is not None and not self.can(by, "owner"):
            raise WorkspaceError(
                f"Only the workspace owner can invite. {by} is not.")
        if role == "owner":
            raise WorkspaceError(
                "Ownership is transferred, not invited — two owners is an "
                "ambiguity nothing downstream can resolve.")

        existing = self.members.get(handle)
        if existing and existing.status == "active":
            raise WorkspaceError(f"{handle} is already in this workspace.")

        member = Member(handle, role, "pending", invited_by=by)
        self.members[handle] = member
        return member

    def respond(self, handle, accept):
        """The invited person answers. Only they can."""
        member = self.members.get(handle)
        if member is None:
            raise WorkspaceError(f"{handle} has no invitation to this workspace.")
        if member.status != "pending":
            raise WorkspaceError(
                f"{handle}'s invitation is already {member.status}.")
        member.status = "active" if accept else "declined"
        return member

    def remove(self, handle, by=None):
        """Revoke access. The owner cannot be removed from their own workspace."""
        if by is not None and not self.can(by, "owner"):
            raise WorkspaceError(f"Only the workspace owner can remove members.")
        if handle == self.owner:
            raise WorkspaceError(
                "The owner cannot be removed — a workspace with no owner has "
                "nobody who can grant access to it again.")
        member = self.members.get(handle)
        if member is None:
            raise WorkspaceError(f"{handle} is not in this workspace.")
        member.status = "removed"
        return member

    # -- permission --------------------------------------------------------

    def can(self, handle, needed):
        member = self.members.get(handle)
        return member is not None and member.can(needed)

    def require(self, handle, needed, what="do that"):
        if not self.can(handle, needed):
            member = self.members.get(handle)
            if member is None or member.status != "active":
                raise WorkspaceError(
                    f"{handle} is not a member of '{self.name}'.")
            raise WorkspaceError(
                f"{handle} is a {member.role} here and needs to be a {needed} "
                f"to {what}.")
        return True

    def active_members(self):
        return sorted((m for m in self.members.values() if m.has_access),
                      key=lambda m: (-rank(m.role), m.handle))

    def pending_members(self):
        return sorted((m for m in self.members.values() if m.status == "pending"),
                      key=lambda m: m.handle)

    def describe(self):
        return (f"{self.name} — {self.owner} — "
                f"{len(self.active_members())} member(s)")

    def __repr__(self):
        return f"<Workspace {self.describe()}>"


__all__ = ["Workspace", "Member", "WorkspaceError", "ROLES", "MEMBERSHIP", "rank"]
