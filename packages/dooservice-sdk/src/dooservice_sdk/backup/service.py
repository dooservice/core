"""Backup and restore for Odoo environments via ephemeral containers."""

from __future__ import annotations

from datetime import UTC, datetime
import math
from pathlib import Path
from typing import Protocol
import uuid
from uuid import UUID

from dooservice_db_agent import BackupRepository
from dooservice_docker import DockerClient
from dooservice_models import (
    DOOSERVICE_NETWORK_NAME,
    MULTIPART_PART_SIZE,
    ODOO_BACKUPS_DIR,
    ODOO_DATA_DIR,
    ODOO_IMAGE,
    Backup,
    BackupSource,
    BackupStatus,
    BackupType,
    Environment,
    StorageType,
)

from ..environments import odoo
from ..errors import (
    BackupFailedError,
    BackupNotDownloadableError,
    BackupNotFoundError,
    InvalidBackupObjectKeyError,
    RestoreFailedError,
)


class BackupBackend(Protocol):
    @property
    def storage_type(self) -> StorageType: ...
    async def upload(self, local_path: Path, env_name: str, filename: str) -> str: ...
    async def download(self, object_key: str, local_path: Path) -> None: ...
    async def delete(self, object_key: str) -> None: ...
    async def presign_download(self, object_key: str, expires_in: int) -> str: ...
    async def size(self, object_key: str) -> int: ...
    async def create_multipart_upload(self, object_key: str) -> str: ...
    async def presign_multipart_part(
        self, object_key: str, upload_id: str, part_number: int, expires_in: int
    ) -> str: ...
    async def complete_multipart(self, object_key: str, upload_id: str, parts: list[dict]) -> None: ...
    async def abort_multipart(self, object_key: str, upload_id: str) -> None: ...


class S3Backend:
    def __init__(self, client) -> None:
        self._client = client

    @property
    def storage_type(self) -> StorageType:
        return StorageType.S3

    async def upload(self, local_path: Path, env_name: str, filename: str) -> str:
        object_key = f"{env_name}/{filename}"
        return await self._client.upload(local_path, object_key=object_key)

    async def download(self, object_key: str, local_path: Path) -> None:
        await self._client.download(object_key, local_path)

    async def delete(self, object_key: str) -> None:
        await self._client.delete(object_key)

    async def presign_download(self, object_key: str, expires_in: int = 3600) -> str:
        return await self._client.presign_download(object_key, expires_in)

    async def size(self, object_key: str) -> int:
        return await self._client.size(object_key)

    async def create_multipart_upload(self, object_key: str) -> str:
        return await self._client.create_multipart_upload(object_key)

    async def presign_multipart_part(self, object_key: str, upload_id: str, part_number: int, expires_in: int) -> str:
        return await self._client.presign_upload_part(object_key, upload_id, part_number, expires_in)

    async def complete_multipart(self, object_key: str, upload_id: str, parts: list[dict]) -> None:
        await self._client.complete_multipart_upload(object_key, upload_id, parts)

    async def abort_multipart(self, object_key: str, upload_id: str) -> None:
        await self._client.abort_multipart_upload(object_key, upload_id)


class BackupService:
    def __init__(
        self,
        docker: DockerClient,
        projects_dir: Path,
        backend: BackupBackend | None = None,
    ) -> None:
        self._docker = docker
        self._projects_dir = projects_dir
        self._backend = backend

    def backups_dir(self, project_name: str, env_name: str) -> Path:
        return self._projects_dir / project_name / env_name / "backups"

    async def create(
        self,
        environment: Environment,
        project_name: str,
        *,
        backup_type: BackupType = BackupType.FULL,
        description: str = "",
        source: BackupSource = BackupSource.MANUAL,
    ) -> Backup:
        host_dir = self.backups_dir(project_name, environment.name)
        host_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"{ts}-{backup_type.value}.zip"
        container_path = f"{ODOO_BACKUPS_DIR}/{filename}"
        storage_type = self._backend.storage_type if self._backend is not None else StorageType.LOCAL

        backup = Backup(
            id=uuid.uuid4(),
            environment_id=environment.id,
            environment_name=environment.name,
            project_name=project_name,
            backup_type=backup_type,
            storage_type=storage_type,
            filename=filename,
            size_bytes=0,
            description=description,
            status=BackupStatus.IN_PROGRESS,
            source=source,
        )
        await BackupRepository.save(backup)

        try:
            result = await self._docker.run_ephemeral(
                image=f"{ODOO_IMAGE}:{environment.odoo_version}",
                command=odoo.build_dump_cmd(
                    environment,
                    container_path,
                    with_filestore=(backup_type == BackupType.FULL),
                ),
                network=DOOSERVICE_NETWORK_NAME,
                volumes={
                    f"odoo_data_{environment.id.hex}": ODOO_DATA_DIR,
                    str(host_dir): ODOO_BACKUPS_DIR,
                },
            )
            if result.exit_code != 0:
                raise BackupFailedError(result.output.strip())

            size = (host_dir / filename).stat().st_size
            stored_filename = filename
            if self._backend is not None:
                stored_filename = await self._backend.upload(host_dir / filename, environment.name, filename)
                (host_dir / filename).unlink(missing_ok=True)

            await BackupRepository.update_status(
                backup.id, BackupStatus.COMPLETED,
                filename=stored_filename,
                size_bytes=size,
            )
            backup.filename = stored_filename
            backup.size_bytes = size
            backup.status = BackupStatus.COMPLETED
        except Exception as exc:
            await BackupRepository.update_status(backup.id, BackupStatus.FAILED)
            backup.status = BackupStatus.FAILED
            if not isinstance(exc, BackupFailedError):
                raise BackupFailedError(str(exc)) from exc
            raise

        return backup

    async def restore(self, backup: Backup, environment: Environment) -> None:
        host_dir = self.backups_dir(backup.project_name, backup.environment_name)
        host_dir.mkdir(parents=True, exist_ok=True)

        if backup.storage_type == StorageType.S3:
            if self._backend is None:
                raise RestoreFailedError("S3 backend not configured")
            local_path = host_dir / backup.filename.split("/")[-1]
            await self._backend.download(backup.filename, local_path)
            container_filename = local_path.name
        else:
            container_filename = backup.filename

        container_path = f"{ODOO_BACKUPS_DIR}/{container_filename}"

        await self._docker.stop_container(environment.container_id)
        try:
            result = await self._docker.run_ephemeral(
                image=f"{ODOO_IMAGE}:{environment.odoo_version}",
                command=odoo.build_load_cmd(environment, container_path),
                network=DOOSERVICE_NETWORK_NAME,
                volumes={
                    f"odoo_data_{environment.id.hex}": ODOO_DATA_DIR,
                    str(host_dir): ODOO_BACKUPS_DIR,
                },
            )
        finally:
            if backup.storage_type == StorageType.S3:
                (host_dir / container_filename).unlink(missing_ok=True)
            await self._docker.start_container(environment.container_id)

        if result.exit_code != 0:
            raise RestoreFailedError(result.output.strip())

    async def get(self, backup_id: UUID) -> Backup:
        backup = await BackupRepository.get(backup_id)
        if backup is None:
            raise BackupNotFoundError(backup_id)
        return backup

    async def list(self, environment_id: UUID) -> list[Backup]:
        return await BackupRepository.list_for_environment(environment_id)

    async def presign_download(self, backup_id: UUID, expires_in: int = 3600) -> str:
        backup = await self.get(backup_id)
        if backup.storage_type != StorageType.S3 or self._backend is None:
            raise BackupNotDownloadableError(backup_id)
        return await self._backend.presign_download(backup.filename, expires_in)


    async def drop(self, backup: Backup, project_name: str) -> None:
        """Delete the physical file and mark the backup as DROPPED.

        The DB record is preserved as permanent history. Only the file on local
        disk or S3 is removed to free storage.
        """
        if backup.storage_type == StorageType.LOCAL:
            host_dir = self.backups_dir(project_name, backup.environment_name)
            (host_dir / backup.filename).unlink(missing_ok=True)
        elif self._backend is not None:
            await self._backend.delete(backup.filename)
        await BackupRepository.update_status(backup.id, BackupStatus.DROPPED)

    async def delete(self, backup: Backup, project_name: str) -> None:
        if backup.storage_type == StorageType.LOCAL:
            host_dir = self.backups_dir(project_name, backup.environment_name)
            (host_dir / backup.filename).unlink(missing_ok=True)
        elif self._backend is not None:
            await self._backend.delete(backup.filename)
        await BackupRepository.delete(backup.id)

    async def presign_multipart_upload(self, environment: Environment, file_size: int, expires_in: int = 3600) -> dict:
        if self._backend is None:
            raise BackupNotDownloadableError(environment.id)
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        object_key = f"{environment.name}/{ts}-uploaded.zip"
        part_count = max(1, math.ceil(file_size / MULTIPART_PART_SIZE))
        upload_id = await self._backend.create_multipart_upload(object_key)
        part_urls = [
            await self._backend.presign_multipart_part(object_key, upload_id, i + 1, expires_in)
            for i in range(part_count)
        ]
        return {
            "object_key": object_key,
            "upload_id":  upload_id,
            "part_urls":  part_urls,
            "part_size":  MULTIPART_PART_SIZE,
        }

    async def complete_multipart_upload(
        self,
        environment: Environment,
        project_name: str,
        object_key: str,
        upload_id: str,
        parts: list[dict],
        file_size: int,
        description: str = "",
    ) -> Backup:
        if self._backend is None:
            raise BackupNotDownloadableError(environment.id)
        expected_prefix = f"{environment.name}/"
        if not object_key.startswith(expected_prefix):
            raise InvalidBackupObjectKeyError(object_key, environment.name)
        await self._backend.complete_multipart(object_key, upload_id, parts)
        size = file_size
        backup = Backup(
            id=uuid.uuid4(),
            environment_id=environment.id,
            environment_name=environment.name,
            project_name=project_name,
            backup_type=BackupType.FULL,
            storage_type=StorageType.S3,
            filename=object_key,
            size_bytes=size,
            description=description,
            status=BackupStatus.COMPLETED,
        )
        await BackupRepository.save(backup)
        return backup
