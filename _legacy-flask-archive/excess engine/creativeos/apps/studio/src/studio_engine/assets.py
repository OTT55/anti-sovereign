"""Assets that keep their versions, so "which file is this?" has an answer.

The problem, stated the way an editor would: a finished piece ends up as
`final.mov`, `final_v2.mov`, `final_v3_REAL.mov` across drives and inboxes, and
six months later nobody can say which one was approved.

The app's `studio_assets` table has one row per asset and no version at all —
`version` appears once in 654 lines. Replacing a file overwrites the row, and
the previous cut is gone from the record even if the bytes still exist
somewhere. That is exactly the failure above, reproduced in software.

## A slot, and the versions in it

An **asset** here is a *slot* — "the trailer", "the grade" — and it holds an
ordered chain of **versions**. Uploading again adds a version; it never
replaces one. So:

* the current version is just the last one,
* every earlier cut is still addressable,
* and a published release can point at a *specific* version rather than at a
  name whose meaning changes underneath it.

Each version carries a content hash, which is what makes "is this the file you
approved?" answerable without anyone's word for it.

## Nothing is deleted

`supersede` and `withdraw` mark; they do not remove. A version that was sent to
a client and then withdrawn still has to be findable, because the client still
has it. Deleting the record does not delete their copy — it only removes your
ability to explain what they are holding.
"""

import hashlib


def content_hash(data):
    """SHA-256 of exactly these bytes."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


class AssetError(Exception):
    """Raised when an asset operation would lose information."""


class Version:
    """One cut of one asset."""

    __slots__ = ("number", "hash", "filename", "media_type", "bytes", "by",
                 "at", "note", "withdrawn")

    def __init__(self, number, hash, filename="", media_type="", bytes=0,
                 by=None, at=None, note=""):
        self.number = number
        self.hash = hash
        self.filename = filename
        self.media_type = media_type
        self.bytes = bytes
        self.by = by
        self.at = at
        self.note = note
        self.withdrawn = False

    @property
    def label(self):
        return f"v{self.number}"

    def describe(self):
        tail = " (withdrawn)" if self.withdrawn else ""
        return f"{self.label} {self.hash[:12]}… {self.filename}{tail}"

    def __repr__(self):
        return f"<Version {self.describe()}>"


class Asset:
    """A named slot and the chain of versions in it."""

    __slots__ = ("id", "project_id", "label", "kind", "versions")

    def __init__(self, id, project_id, label, kind="video"):
        if not (label or "").strip():
            raise AssetError("An asset needs a label.")
        self.id = id
        self.project_id = project_id
        self.label = label
        self.kind = kind
        self.versions = []

    def add(self, data, filename="", media_type="", by=None, at=None, note=""):
        """Add a version. Never replaces; the chain only grows.

        Re-uploading identical bytes is refused rather than silently recorded.
        A version that changes nothing is noise in a history whose entire value
        is that every entry means something happened.
        """
        digest = content_hash(data)
        if self.versions and self.current.hash == digest:
            raise AssetError(
                f"'{self.label}' is already at this exact content ({self.current.label}). "
                "Nothing changed, so there is no new version to record.")
        version = Version(len(self.versions) + 1, digest, filename, media_type,
                          len(data) if data is not None else 0, by, at, note)
        self.versions.append(version)
        return version

    @property
    def current(self):
        """The latest version that has not been withdrawn."""
        for version in reversed(self.versions):
            if not version.withdrawn:
                return version
        return None

    def version(self, number):
        for version in self.versions:
            if version.number == number:
                return version
        raise AssetError(f"'{self.label}' has no {f'v{number}'}.")

    def withdraw(self, number, why=""):
        """Mark a version as not to be used. It stays in the record.

        Removing it would leave a gap in the numbering and no explanation for
        it, which is worse than an entry that says plainly it was pulled.
        """
        version = self.version(number)
        version.withdrawn = True
        version.note = why or version.note
        return version

    def verify(self, number, data):
        return self.version(number).hash == content_hash(data)

    def history(self):
        return list(self.versions)

    def describe(self):
        current = self.current
        return (f"{self.label} ({self.kind}) — "
                f"{len(self.versions)} version(s), current "
                f"{current.label if current else 'none'}")

    def __repr__(self):
        return f"<Asset {self.describe()}>"


__all__ = ["Asset", "Version", "AssetError", "content_hash"]
