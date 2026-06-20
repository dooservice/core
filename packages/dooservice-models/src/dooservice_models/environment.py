"""Environment model — lifecycle + runtime state separation."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
import uuid

import msgspec

from .constants import DOOSERVICE_NETWORK_NAME, PGDOG_CONTAINER_NAME, PGDOG_PORT
from .domain import CustomDomain
from .project import ProjectId

EnvironmentId = uuid.UUID


class LifecycleState(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class RuntimeState(StrEnum):
    PROVISIONING = "provisioning"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


class EnvironmentMode(StrEnum):
    PRODUCTION = "production"
    DEVELOPMENT = "development"


class EnvironmentConfig(msgspec.Struct):
    pg_db_name: str = ""
    pg_db_user: str = ""
    pg_db_password: str = ""

    pg_db_host: str = PGDOG_CONTAINER_NAME
    pg_db_port: int = PGDOG_PORT

    admin_email: str = ""
    admin_password: str = ""
    timezone: str = "America/Lima"
    language: str = "es_PE"
    environment: dict[str, str] = msgspec.field(default_factory=dict)

    primary_domain: str = ""
    custom_domain: CustomDomain | None = None
    proxy_network_name: str = DOOSERVICE_NETWORK_NAME

    base_workers: int = 0
    extra_workers: int = 0

    auto_backup_enabled: bool = True


class Environment(msgspec.Struct):
    id: EnvironmentId
    name: str
    project_id: ProjectId
    mode: EnvironmentMode

    branch: str | None = None
    commit: str | None = None

    runtime_state: RuntimeState = RuntimeState.PROVISIONING
    lifecycle_state: LifecycleState = LifecycleState.ACTIVE

    odoo_version:   str  = "19.0"
    has_repository: bool = False
    container_id: str | None = None

    config: EnvironmentConfig = msgspec.field(default_factory=EnvironmentConfig)

    created_at: datetime = msgspec.field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = msgspec.field(default_factory=lambda: datetime.now(UTC))

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC)

    def _transition(self, runtime: RuntimeState) -> None:
        self.runtime_state = runtime
        self.touch()

    def provision(self) -> None:
        self._transition(RuntimeState.PROVISIONING)

    def start(self) -> None:
        self._transition(RuntimeState.RUNNING)

    def stop(self) -> None:
        self._transition(RuntimeState.STOPPED)

    def fail(self) -> None:
        self._transition(RuntimeState.FAILED)

    def archive(self) -> None:
        self._transition(RuntimeState.STOPPED)
        self.lifecycle_state = LifecycleState.ARCHIVED
        self.container_id = None
