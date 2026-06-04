"""Project model: Project, ProjectId."""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

import msgspec

ProjectId = uuid.UUID


class Project(msgspec.Struct):
    """A customer project — owns N environments (prod, staging, dev)."""

    id:             ProjectId
    name:           str
    has_repository: bool
    created_at:     datetime
    updated_at:     datetime
    odoo_version:   str        = "19.0"
    timezone:       str        = "UTC"
    language:       str        = "en_US"
    repo_full_name: str | None = None

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC)
