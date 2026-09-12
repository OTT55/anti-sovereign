"""The Platform Engine — *"Everything shared."*

Constitution v2.0: *"Authentication. Organizations. Permissions. Realtime.
Notifications. Billing. Marketplace. Plugin infrastructure. Developer SDK."*

This exists because of the boundary violation `BUILD_PLAN.md` names: today
FrameVault is both an application *and* the de-facto identity provider for
FilmCrew and RightsForge, which call its `/api/authenticate`. Under v2.0 that
job belongs to the platform, so every application gets it and none owns it.

Built here: **accounts, organizations, membership, roles and permissions**, plus
notifications riding the Event Engine.

Deliberately **not** built: password hashing, session tokens, billing. Those are
not architecture, they are a library call and a payment provider, and inventing
either badly would be worse than not having them. What the platform owes the
ecosystem is the *shape* — who exists, which organization they belong to, what
they may do — and that shape is what is here. `authenticate()` takes a verifier
callback so a real credential store plugs in without this module ever handling a
secret.
"""

from ..graph import ids

ACCOUNT = "ACC"
ORG = "ORG"

#: Roles in ascending order of authority. Comparing by index means a check is
#: "at least this role" rather than an exact match, so adding a role later does
#: not require revisiting every call site.
ROLES = ("viewer", "contributor", "editor", "admin", "owner")

#: What each role may do. A permission is a plain string so applications can
#: declare their own without the platform knowing what they mean.
ROLE_PERMISSIONS = {
    "viewer": {"read"},
    "contributor": {"read", "create"},
    "editor": {"read", "create", "update"},
    "admin": {"read", "create", "update", "delete", "invite"},
    "owner": {"read", "create", "update", "delete", "invite", "transfer", "billing"},
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id          TEXT PRIMARY KEY,
    handle      TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL DEFAULT '',
    entity_id   TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS organizations (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memberships (
    org_id      TEXT NOT NULL REFERENCES organizations(id),
    account_id  TEXT NOT NULL REFERENCES accounts(id),
    role        TEXT NOT NULL,
    joined_at   TEXT NOT NULL,
    PRIMARY KEY (org_id, account_id)
);

CREATE TABLE IF NOT EXISTS org_spaces (
    org_id      TEXT NOT NULL REFERENCES organizations(id),
    space_id TEXT NOT NULL,
    PRIMARY KEY (org_id, space_id)
);

CREATE INDEX IF NOT EXISTS idx_membership_account ON memberships(account_id);
"""


class PlatformError(Exception):
    """Raised when an operation would make the platform's state incoherent."""


class Account:
    __slots__ = ("id", "handle", "display_name", "entity_id", "created_at")

    def __init__(self, id, handle, display_name, entity_id, created_at):
        self.id = id
        self.handle = handle
        self.display_name = display_name
        self.entity_id = entity_id
        self.created_at = created_at

    def __repr__(self):
        return f"<Account @{self.handle}>"


class Organization:
    __slots__ = ("id", "name", "slug", "created_at")

    def __init__(self, id, name, slug, created_at):
        self.id = id
        self.name = name
        self.slug = slug
        self.created_at = created_at

    def __repr__(self):
        return f"<Organization {self.slug}>"


class PlatformEngine:
    def __init__(self, conn, bus=None):
        self.conn = conn
        self.bus = bus
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # -- accounts ----------------------------------------------------------

    def create_account(self, handle, display_name="", entity_id=None):
        handle = handle.strip().lstrip("@").lower()
        if not handle:
            raise PlatformError("A handle is required.")
        if self.account_by_handle(handle) is not None:
            raise PlatformError(f"@{handle} is already taken.")
        account = Account(ids.new_id(ACCOUNT), handle, display_name or handle,
                          entity_id, ids.now())
        self.conn.execute(
            """INSERT INTO accounts (id, handle, display_name, entity_id, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (account.id, account.handle, account.display_name, entity_id, account.created_at),
        )
        self.conn.commit()
        self._emit("account.created", {"account_id": account.id, "handle": handle})
        return account

    def account_by_handle(self, handle):
        row = self.conn.execute(
            "SELECT * FROM accounts WHERE handle = ?", (handle.strip().lstrip("@").lower(),)
        ).fetchone()
        return _to_account(row) if row else None

    def get_account(self, account_id):
        row = self.conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        return _to_account(row) if row else None

    def authenticate(self, handle, verifier):
        """Resolve a handle to an account **if** `verifier(account)` says so.

        The platform never sees a credential. `verifier` is supplied by whatever
        actually holds them, which keeps secret-handling out of this module
        entirely — and means a real credential store can be swapped in without
        touching a line here.
        """
        account = self.account_by_handle(handle)
        if account is None:
            return None
        try:
            return account if verifier(account) else None
        except Exception:
            return None   # a verifier that throws has not authenticated anyone

    # -- organizations -----------------------------------------------------

    def create_organization(self, name, slug=None, owner=None):
        slug = (slug or name).strip().lower().replace(" ", "-")
        if self.organization_by_slug(slug) is not None:
            raise PlatformError(f"'{slug}' is already taken.")
        org = Organization(ids.new_id(ORG), name, slug, ids.now())
        self.conn.execute(
            "INSERT INTO organizations (id, name, slug, created_at) VALUES (?, ?, ?, ?)",
            (org.id, org.name, org.slug, org.created_at),
        )
        self.conn.commit()
        if owner is not None:
            self.add_member(org.id, owner, role="owner")
        self._emit("organization.created", {"org_id": org.id, "slug": slug})
        return org

    def organization_by_slug(self, slug):
        row = self.conn.execute(
            "SELECT * FROM organizations WHERE slug = ?", (slug.strip().lower(),)
        ).fetchone()
        return _to_org(row) if row else None

    def add_member(self, org_id, account_id, role="contributor"):
        if role not in ROLES:
            raise PlatformError(f"Unknown role '{role}'. Known roles: {', '.join(ROLES)}.")
        self.conn.execute(
            """INSERT OR REPLACE INTO memberships (org_id, account_id, role, joined_at)
               VALUES (?, ?, ?, ?)""",
            (org_id, account_id, role, ids.now()),
        )
        self.conn.commit()
        self._emit("member.added", {"org_id": org_id, "account_id": account_id, "role": role})

    def remove_member(self, org_id, account_id):
        """Remove a member, refusing to leave an organization ownerless.

        An organization nobody can administer is unrecoverable without direct
        database access, so this is a state the platform must not allow.
        """
        if self.role_of(org_id, account_id) == "owner":
            owners = [m for m in self.members(org_id) if m[1] == "owner"]
            if len(owners) <= 1:
                raise PlatformError(
                    "Cannot remove the last owner — transfer ownership first, "
                    "or the organization becomes unadministrable."
                )
        self.conn.execute(
            "DELETE FROM memberships WHERE org_id = ? AND account_id = ?",
            (org_id, account_id),
        )
        self.conn.commit()
        self._emit("member.removed", {"org_id": org_id, "account_id": account_id})

    def members(self, org_id):
        rows = self.conn.execute(
            "SELECT account_id, role FROM memberships WHERE org_id = ? ORDER BY joined_at ASC",
            (org_id,),
        ).fetchall()
        return [(r["account_id"], r["role"]) for r in rows]

    def organizations_for(self, account_id):
        rows = self.conn.execute(
            """SELECT o.* FROM organizations o
               JOIN memberships m ON m.org_id = o.id
               WHERE m.account_id = ? ORDER BY o.created_at ASC""",
            (account_id,),
        ).fetchall()
        return [_to_org(r) for r in rows]

    # -- permissions -------------------------------------------------------

    def role_of(self, org_id, account_id):
        row = self.conn.execute(
            "SELECT role FROM memberships WHERE org_id = ? AND account_id = ?",
            (org_id, account_id),
        ).fetchone()
        return row["role"] if row else None

    def can(self, org_id, account_id, permission):
        role = self.role_of(org_id, account_id)
        return permission in ROLE_PERMISSIONS.get(role, set()) if role else False

    def has_at_least(self, org_id, account_id, role):
        """Is this member's role at least as senior as `role`?"""
        current = self.role_of(org_id, account_id)
        if current is None:
            return False
        return ROLES.index(current) >= ROLES.index(role)

    def require(self, org_id, account_id, permission):
        if not self.can(org_id, account_id, permission):
            role = self.role_of(org_id, account_id) or "not a member"
            raise PlatformError(
                f"Permission '{permission}' denied: the account is {role}."
            )

    # -- spaces ---------------------------------------------------------

    def attach_space(self, org_id, space_id):
        """Put a space under an organization, so access is inherited."""
        self.conn.execute(
            "INSERT OR IGNORE INTO org_spaces (org_id, space_id) VALUES (?, ?)",
            (org_id, space_id),
        )
        self.conn.commit()

    def spaces_for(self, org_id):
        rows = self.conn.execute(
            "SELECT space_id FROM org_spaces WHERE org_id = ?", (org_id,)
        ).fetchall()
        return [r["space_id"] for r in rows]

    def can_access_space(self, account_id, space_id, permission="read"):
        rows = self.conn.execute(
            "SELECT org_id FROM org_spaces WHERE space_id = ?", (space_id,)
        ).fetchall()
        if not rows:
            return True   # unattached spaces are unrestricted
        return any(self.can(r["org_id"], account_id, permission) for r in rows)

    # -- notifications -----------------------------------------------------

    def notify(self, account_id, message, kind="info"):
        """Notifications ride the Event Engine rather than a second mechanism."""
        return self._emit("notification.sent",
                          {"account_id": account_id, "message": message, "kind": kind})

    def _emit(self, kind, payload):
        if self.bus is None:
            return None
        return self.bus.publish("", kind, payload.get("account_id", ""), payload,
                                source="creativeos.platform")


def _to_account(row):
    return Account(row["id"], row["handle"], row["display_name"],
                   row["entity_id"], row["created_at"])


def _to_org(row):
    return Organization(row["id"], row["name"], row["slug"], row["created_at"])
