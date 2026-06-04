from __future__ import annotations

from uuid import UUID

from dooservice_models import Backup, BackupSource, BackupStatus

from ..models import BackupModel


class BackupRepository:
    @staticmethod
    async def save(backup: Backup) -> None:
        await BackupModel.create(
            id=backup.id,
            environment_id=backup.environment_id,
            environment_name=backup.environment_name,
            project_name=backup.project_name,
            backup_type=backup.backup_type.value,
            storage_type=backup.storage_type.value,
            filename=backup.filename,
            size_bytes=backup.size_bytes,
            description=backup.description,
            status=backup.status.value,
            source=backup.source.value,
        )

    @staticmethod
    async def update_status(
        backup_id: UUID,
        status: BackupStatus,
        *,
        filename: str | None = None,
        size_bytes: int | None = None,
    ) -> None:
        updates: dict = {"status": status.value}
        if filename is not None:
            updates["filename"] = filename
        if size_bytes is not None:
            updates["size_bytes"] = size_bytes
        await BackupModel.filter(id=backup_id).update(**updates)

    @staticmethod
    async def get(backup_id: UUID) -> Backup | None:
        row = await BackupModel.get_or_none(id=backup_id)
        return row.to_struct() if row else None

    @staticmethod
    async def list_for_environment(environment_id: UUID) -> list[Backup]:
        rows = await BackupModel.filter(environment_id=environment_id).order_by("-created_at")
        return [r.to_struct() for r in rows]

    @staticmethod
    async def mark_dropped(backup_id: UUID) -> None:
        await BackupModel.filter(id=backup_id).update(status=BackupStatus.DROPPED.value)

    @staticmethod
    async def get_latest_scheduled_completed(environment_id: UUID, exclude_id: UUID) -> Backup | None:
        """Return the most recent completed scheduled backup, excluding the given id."""
        row = await BackupModel.filter(
            environment_id=environment_id,
            source=BackupSource.SCHEDULED.value,
            status=BackupStatus.COMPLETED.value,
        ).exclude(id=exclude_id).order_by("-created_at").first()
        return row.to_struct() if row else None

    @staticmethod
    async def list_completed_scheduled(environment_id: UUID) -> list[Backup]:
        rows = await BackupModel.filter(
            environment_id=environment_id,
            source=BackupSource.SCHEDULED.value,
            status=BackupStatus.COMPLETED.value,
        ).order_by("-created_at")
        return [row.to_struct() for row in rows]

    @staticmethod
    async def get_latest() -> Backup | None:
        row = await BackupModel.all().order_by("-created_at").first()
        return row.to_struct() if row else None

    @staticmethod
    async def delete(backup_id: UUID) -> None:
        await BackupModel.filter(id=backup_id).delete()
