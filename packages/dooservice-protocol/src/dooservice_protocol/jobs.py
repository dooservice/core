"""Job kind catalog and per-job argument structs."""

from __future__ import annotations

from enum import StrEnum
import uuid

import msgspec


class JobKind(StrEnum):
    ENV_PROVISION       = "env.provision"
    ENV_START           = "env.start"
    ENV_STOP            = "env.stop"
    ENV_DELETE          = "env.delete"
    ENV_CLONE           = "env.clone"
    BACKUP_CREATE       = "backup.create"
    BACKUP_RESTORE      = "backup.restore"
    PROJECT_CREATE      = "project.create"
    PROJECT_DELETE      = "project.delete"
    QUERY_PROJECTS      = "query.projects"
    QUERY_ENVIRONMENTS  = "query.environments"
    QUERY_BACKUPS       = "query.backups"
    QUERY_BACKUP_DOWNLOAD_URL  = "query.backup.download_url"
    QUERY_BACKUP_MULTIPART_URL = "query.backup.multipart_url"
    BACKUP_MULTIPART_COMPLETE  = "backup.multipart.complete"
    PROJECT_KEY_SETUP    = "project_key.setup"
    SUBMODULE_KEY_SETUP  = "submodule_key.setup"
    SUBMODULE_KEY_DELETE = "submodule_key.delete"
    ENV_UPDATE_WORKERS   = "env.update_workers"
    ENV_REBUILD          = "env.rebuild"
    ENV_ROLLBACK         = "env.rollback"
    QUERY_DEPLOYMENTS    = "query.deployments"


# ── Per-kind argument structs ─────────────────────────────────────────────────


class EnvProvisionArgs(msgspec.Struct):
    project_name:   str
    mode:           str              = "development"
    base_domain:    str              = ""
    environment_id: uuid.UUID | None = None
    odoo_version:   str | None       = None
    admin_email:    str              = ""
    admin_password: str              = ""
    timezone:       str | None       = None
    language:       str | None       = None
    repo_full_name: str | None       = None
    branch:         str | None       = None
    has_repository: bool             = False
    neutralize:     bool             = True


class EnvStartArgs(msgspec.Struct):
    environment_id: str


class EnvStopArgs(msgspec.Struct):
    environment_id: str


class EnvDeleteArgs(msgspec.Struct):
    environment_id: str


class EnvCloneArgs(msgspec.Struct):
    source_environment_id: str
    mode:                  str              = "development"
    base_domain:           str              = ""
    environment_id:        uuid.UUID | None = None
    branch:                str | None       = None
    neutralize:            bool             = True


class BackupCreateArgs(msgspec.Struct):
    environment_id: str
    backup_type: str = "full"  # full | database
    description: str = ""


class BackupRestoreArgs(msgspec.Struct):
    environment_id: str
    backup_id: str


class BackupDownloadUrlArgs(msgspec.Struct):
    backup_id:  str
    expires_in: int = 3600


class MultipartPart(msgspec.Struct):
    PartNumber: int
    ETag:       str


class BackupMultipartUrlArgs(msgspec.Struct):
    environment_id: str
    file_size:      int
    expires_in:     int = 3600


class BackupMultipartCompleteArgs(msgspec.Struct):
    environment_id: str
    object_key:     str
    upload_id:      str
    parts:          list[MultipartPart]
    file_size:      int
    description:    str = ""


class ProjectCreateArgs(msgspec.Struct):
    name:           str
    has_repository: bool       = False
    repo_full_name: str | None = None
    odoo_version:   str        = "19.0"
    timezone:       str        = "UTC"
    language:       str        = "en_US"


class ProjectDeleteArgs(msgspec.Struct):
    name: str


class QueryEnvironmentsArgs(msgspec.Struct):
    project_name: str


class QueryBackupsArgs(msgspec.Struct):
    environment_id: str


class DomainSetArgs(msgspec.Struct):
    environment_id: str
    domain: str


class DomainRemoveArgs(msgspec.Struct):
    environment_id: str


class DomainVerifyArgs(msgspec.Struct):
    environment_id: str


class EnvLogsArgs(msgspec.Struct):
    environment_id: str
    tail: int = 200



class ProjectKeySetupArgs(msgspec.Struct):
    project_name: str


class SubmoduleKeySetupArgs(msgspec.Struct):
    project_name: str
    repo_url:     str


class SubmoduleKeyDeleteArgs(msgspec.Struct):
    project_name: str
    repo_url:     str


class GitPullArgs(msgspec.Struct):
    environment_id: str
    branch:         str | None = None
    commit:         str | None = None


class WorkersUpdateArgs(msgspec.Struct):
    environment_id: str
    workers:        int


class EnvRebuildArgs(msgspec.Struct):
    environment_id: str


class EnvRollbackArgs(msgspec.Struct):
    environment_id: str
    revision:       int


class QueryDeploymentsArgs(msgspec.Struct):
    environment_id: str
