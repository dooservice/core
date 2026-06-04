from __future__ import annotations

from typing import Protocol
import uuid


class BackupSchedulerProtocol(Protocol):
    def register(self, env_id: uuid.UUID, project_id: uuid.UUID, timezone: str) -> None: ...
    def unregister(self, env_id: uuid.UUID) -> None: ...
