from __future__ import annotations

from enum import StrEnum
import uuid

import msgspec


class BackupType(StrEnum):
    FULL = "full"  # DB + filestore
    DATABASE = "database"  # DB only (--no-filestore)


class StorageType(StrEnum):
    LOCAL = "local"
    S3 = "s3"


class BackupStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED   = "completed"
    FAILED      = "failed"
    DROPPED     = "dropped"


class BackupSource(StrEnum):
    MANUAL    = "manual"
    SCHEDULED = "scheduled"
    PRE_DEPLOY = "pre_deploy"


class Backup(msgspec.Struct):
    id: uuid.UUID
    environment_id: uuid.UUID
    environment_name: str
    project_name: str
    backup_type: BackupType
    storage_type: StorageType
    filename: str  # local filename or S3 object key
    size_bytes: int = 0
    description: str = ""
    status: BackupStatus = BackupStatus.COMPLETED
    source: BackupSource = BackupSource.MANUAL
    created_at: str = ""
