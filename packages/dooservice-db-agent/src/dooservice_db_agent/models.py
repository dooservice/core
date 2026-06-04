"""Tortoise ORM models bridged to msgspec domain structs."""

from __future__ import annotations

from typing import ClassVar
import uuid

import msgspec
from tortoise import fields
from tortoise.models import Model

from dooservice_models import (
    Backup,
    BackupSource,
    BackupStatus,
    BackupType,
    DeploymentStatus,
    Environment,
    EnvironmentConfig,
    EnvironmentDeployment,
    EnvironmentMode,
    LifecycleState,
    Project,
    ProxyConfig,
    RuntimeState,
    StorageType,
)


class ProjectModel(Model):
    id             = fields.UUIDField(pk=True)
    name           = fields.CharField(max_length=255, unique=True)
    has_repository = fields.BooleanField(default=False)
    repo_full_name = fields.CharField(max_length=512, null=True, default=None)
    odoo_version   = fields.CharField(max_length=32, default="19.0")
    timezone       = fields.CharField(max_length=64, default="UTC")
    language       = fields.CharField(max_length=16, default="en_US")
    created_at     = fields.DatetimeField()
    updated_at     = fields.DatetimeField()

    class Meta:
        table = "projects"

    @classmethod
    def from_struct(cls, project: Project) -> ProjectModel:
        return cls(
            id=project.id,
            name=project.name,
            has_repository=project.has_repository,
            repo_full_name=project.repo_full_name,
            odoo_version=project.odoo_version,
            timezone=project.timezone,
            language=project.language,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    def to_struct(self) -> Project:
        return Project(
            id=self.id,
            name=self.name,
            has_repository=self.has_repository,
            repo_full_name=self.repo_full_name,
            odoo_version=self.odoo_version,
            timezone=self.timezone,
            language=self.language,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class EnvironmentModel(Model):
    id = fields.UUIDField(pk=True)
    project: fields.ForeignKeyRelation[ProjectModel] = fields.ForeignKeyField(
        "models.ProjectModel",
        related_name="environments",
        on_delete=fields.CASCADE,
    )
    name = fields.CharField(max_length=255)
    mode           = fields.CharEnumField(EnvironmentMode, max_length=32)
    odoo_version   = fields.CharField(max_length=32)
    has_repository = fields.BooleanField(default=False)
    branch = fields.CharField(max_length=255, null=True, default=None)
    commit = fields.CharField(max_length=64,  null=True, default=None)
    runtime_state = fields.CharEnumField(RuntimeState, max_length=32, default=RuntimeState.PROVISIONING)
    lifecycle_state = fields.CharEnumField(LifecycleState, max_length=32, default=LifecycleState.ACTIVE)
    container_id = fields.CharField(max_length=128, null=True)
    config = fields.JSONField(default=dict)
    created_at = fields.DatetimeField()
    updated_at = fields.DatetimeField()

    class Meta:
        table = "environments"
        unique_together = (("project", "name"),)

    @classmethod
    def from_struct(cls, e: Environment) -> EnvironmentModel:
        return cls(
            id=e.id,
            project_id=e.project_id,
            name=e.name,
            mode=e.mode,
            odoo_version=e.odoo_version,
            has_repository=e.has_repository,
            branch=e.branch,
            commit=e.commit,
            runtime_state=e.runtime_state,
            lifecycle_state=e.lifecycle_state,
            container_id=e.container_id,
            config=msgspec.to_builtins(e.config),
            created_at=e.created_at,
            updated_at=e.updated_at,
        )

    def to_struct(self) -> Environment:
        return Environment(
            id=self.id,
            project_id=self.project_id,
            name=self.name,
            mode=self.mode,
            odoo_version=self.odoo_version,
            has_repository=self.has_repository,
            branch=self.branch,
            commit=self.commit,
            runtime_state=self.runtime_state,
            lifecycle_state=self.lifecycle_state,
            container_id=self.container_id,
            config=msgspec.convert(self.config, type=EnvironmentConfig),
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class BackupModel(Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    environment_id = fields.UUIDField()
    environment_name = fields.CharField(max_length=255)
    project_name = fields.CharField(max_length=255)
    backup_type = fields.CharField(max_length=20)
    storage_type = fields.CharField(max_length=20)
    filename = fields.TextField()
    size_bytes = fields.BigIntField(default=0)
    description = fields.TextField(default="")
    status = fields.CharField(max_length=20, default="completed")
    source = fields.CharField(max_length=20, default="manual")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "backups"
        ordering: ClassVar = ["-created_at"]

    def to_struct(self) -> Backup:
        return Backup(
            id=self.id,
            environment_id=self.environment_id,
            environment_name=self.environment_name,
            project_name=self.project_name,
            backup_type=BackupType(self.backup_type),
            storage_type=StorageType(self.storage_type),
            filename=self.filename,
            size_bytes=self.size_bytes,
            description=self.description,
            status=BackupStatus(self.status),
            source=BackupSource(self.source),
            created_at=self.created_at.isoformat() if self.created_at else "",
        )


class EnvironmentDeploymentModel(Model):
    id              = fields.UUIDField(pk=True, default=uuid.uuid4)
    environment_id  = fields.UUIDField()
    revision        = fields.IntField()
    triggered_by    = fields.CharField(max_length=64)
    commit_before   = fields.CharField(max_length=64, null=True)
    commit_after    = fields.CharField(max_length=64, null=True)
    branch          = fields.CharField(max_length=255, null=True)
    config_snapshot = fields.JSONField()
    backup_id       = fields.UUIDField(null=True)
    status          = fields.CharField(max_length=32)
    created_at      = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table    = "environment_deployments"
        ordering: ClassVar = ["-revision"]

    def to_struct(self) -> EnvironmentDeployment:
        return EnvironmentDeployment(
            id=self.id,
            environment_id=self.environment_id,
            revision=self.revision,
            triggered_by=self.triggered_by,
            commit_before=self.commit_before,
            commit_after=self.commit_after,
            branch=self.branch,
            config_snapshot=self.config_snapshot,
            backup_id=self.backup_id,
            status=DeploymentStatus(self.status),
            created_at=self.created_at.isoformat() if self.created_at else "",
        )


class ProxyConfigModel(Model):
    """Singleton (id=1) holding the global Traefik proxy config."""

    id = fields.IntField(pk=True)
    payload = fields.JSONField(default=dict)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "proxy_config"

    @classmethod
    def from_struct(cls, proxy_config: ProxyConfig) -> ProxyConfigModel:
        return cls(id=1, payload=msgspec.to_builtins(proxy_config))

    def to_struct(self) -> ProxyConfig:
        return msgspec.convert(self.payload, type=ProxyConfig)
