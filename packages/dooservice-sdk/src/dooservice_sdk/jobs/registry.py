from __future__ import annotations

from .handlers.backup import (
    BackupCreate,
    BackupMultipartComplete,
    BackupRestore,
    QueryBackupDownloadUrl,
    QueryBackupMultipartUrl,
)
from .handlers.deployment import EnvRollback, QueryDeployments
from .handlers.domain import DomainRemove, DomainSet, DomainVerify
from .handlers.env import EnvClone, EnvDelete, EnvProvision, EnvRebuild, EnvStart, EnvStop, WorkersUpdate
from .handlers.git import GitPull, ProjectKeySetup, SubmoduleKeyDelete, SubmoduleKeySetup
from .handlers.logs import EnvLogs
from .handlers.project import ProjectCreate, ProjectDelete, QueryBackups, QueryEnvironments, QueryProjects

JOBS: dict[str, type] = {
    "project.create":      ProjectCreate,
    "project.delete":      ProjectDelete,
    "query.projects":      QueryProjects,
    "query.environments":  QueryEnvironments,
    "query.backups":       QueryBackups,
    "env.provision":       EnvProvision,
    "env.clone":           EnvClone,
    "env.start":           EnvStart,
    "env.stop":            EnvStop,
    "env.delete":          EnvDelete,
    "env.update_workers":  WorkersUpdate,
    "env.rebuild":         EnvRebuild,
    "env.rollback":        EnvRollback,
    "env.logs":            EnvLogs,
    "project_key.setup":    ProjectKeySetup,
    "submodule_key.setup":  SubmoduleKeySetup,
    "submodule_key.delete": SubmoduleKeyDelete,
    "git.pull":            GitPull,
    "domain.set":          DomainSet,
    "domain.remove":       DomainRemove,
    "domain.verify":       DomainVerify,
    "backup.create":              BackupCreate,
    "backup.restore":             BackupRestore,
    "backup.multipart.complete":  BackupMultipartComplete,
    "query.backup.download_url":  QueryBackupDownloadUrl,
    "query.backup.multipart_url": QueryBackupMultipartUrl,
    "query.deployments":          QueryDeployments,
}
