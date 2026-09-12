"""The Storage Engine — *"Files. Media. Metadata. Versions. Snapshots."*

Part of Phase 10. Content-addressed blobs (SHA-256 of the bytes) with a walkable
version chain per logical file.
"""

from .store import StorageEngine, StoredFile, digest_of

__all__ = ["StorageEngine", "StoredFile", "digest_of"]
