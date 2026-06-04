from __future__ import annotations

from uuid import UUID

import msgspec

from dooservice_models import BackupType
from dooservice_protocol import (
    BackupCreateArgs,
    BackupDownloadUrlArgs,
    BackupMultipartCompleteArgs,
    BackupMultipartUrlArgs,
    BackupRestoreArgs,
)

from ..context import JobContext


class BackupCreate:
    async def run(self, ctx: JobContext) -> dict:
        args    = msgspec.convert(ctx.args, BackupCreateArgs)
        env     = await ctx.sdk.environments.get(UUID(args.environment_id))
        project = await ctx.sdk.projects.get_by_id(env.project_id)
        backup  = await ctx.sdk.backups.create(
            env, project.name,
            backup_type=BackupType(args.backup_type),
            description=args.description,
        )
        return {
            "backup_id":    str(backup.id),
            "filename":     backup.filename,
            "size_bytes":   backup.size_bytes,
            "storage_type": backup.storage_type.value,
        }


class BackupRestore:
    async def run(self, ctx: JobContext) -> dict:
        args   = msgspec.convert(ctx.args, BackupRestoreArgs)
        env    = await ctx.sdk.environments.get(UUID(args.environment_id))
        backup = await ctx.sdk.backups.get(UUID(args.backup_id))
        await ctx.sdk.backups.restore(backup, env)
        return {"restored": True, "backup_id": args.backup_id}


class QueryBackupDownloadUrl:
    async def run(self, ctx: JobContext) -> dict:
        args         = msgspec.convert(ctx.args, BackupDownloadUrlArgs)
        download_url = await ctx.sdk.backups.presign_download(UUID(args.backup_id), expires_in=args.expires_in)
        return {"download_url": download_url}


class QueryBackupMultipartUrl:
    async def run(self, ctx: JobContext) -> dict:
        args        = msgspec.convert(ctx.args, BackupMultipartUrlArgs)
        environment = await ctx.sdk.environments.get(UUID(args.environment_id))
        return await ctx.sdk.backups.presign_multipart_upload(environment, args.file_size, args.expires_in)


class BackupMultipartComplete:
    async def run(self, ctx: JobContext) -> dict:
        args        = msgspec.convert(ctx.args, BackupMultipartCompleteArgs)
        environment = await ctx.sdk.environments.get(UUID(args.environment_id))
        project     = await ctx.sdk.projects.get_by_id(environment.project_id)
        parts       = [{"PartNumber": p.PartNumber, "ETag": p.ETag} for p in args.parts]
        backup      = await ctx.sdk.backups.complete_multipart_upload(
            environment, project.name, args.object_key, args.upload_id, parts, args.file_size, args.description
        )
        return {
            "backup_id":    str(backup.id),
            "filename":     backup.filename,
            "size_bytes":   backup.size_bytes,
            "storage_type": backup.storage_type.value,
        }
