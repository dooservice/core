from __future__ import annotations

from uuid import UUID

import msgspec

from dooservice_protocol import ProjectCreateArgs, ProjectDeleteArgs, QueryBackupsArgs, QueryEnvironmentsArgs

from ..context import JobContext


class ProjectCreate:
    async def run(self, ctx: JobContext) -> dict:
        args    = msgspec.convert(ctx.args, ProjectCreateArgs)
        await ctx.progress("Creating project", 0)
        project = await ctx.sdk.projects.create(
            args.name,
            has_repository=args.has_repository,
            repo_full_name=args.repo_full_name,
            odoo_version=args.odoo_version,
            timezone=args.timezone,
            language=args.language,
        )
        public_key = ""
        if args.has_repository:
            await ctx.progress("Setting up deploy key", 50)
            public_key = ctx.sdk.git.setup_project_key(args.name)["public_key"]
        return {
            "project_id":     str(project.id),
            "name":           project.name,
            "odoo_version":   project.odoo_version,
            "timezone":       project.timezone,
            "language":       project.language,
            "repo_full_name": project.repo_full_name,
            "created_at":     project.created_at.isoformat(),
            "public_key":     public_key,
        }


class ProjectDelete:
    async def run(self, ctx: JobContext) -> dict:
        args         = msgspec.convert(ctx.args, ProjectDeleteArgs)
        environments = await ctx.sdk.environments.list(args.name)
        for env in environments:
            await ctx.sdk.environments.delete(env.id)
        await ctx.sdk.projects.delete(args.name)
        return {"deleted": True, "name": args.name}


class QueryProjects:
    async def run(self, ctx: JobContext) -> dict:
        projects = await ctx.sdk.projects.list_all()
        return {"projects": [msgspec.to_builtins(project) for project in projects]}


class QueryEnvironments:
    async def run(self, ctx: JobContext) -> dict:
        args         = msgspec.convert(ctx.args, QueryEnvironmentsArgs)
        environments = await ctx.sdk.environments.list(args.project_name)
        return {"environments": [msgspec.to_builtins(env) for env in environments]}


class QueryBackups:
    async def run(self, ctx: JobContext) -> dict:
        args    = msgspec.convert(ctx.args, QueryBackupsArgs)
        backups = await ctx.sdk.backups.list(UUID(args.environment_id))
        return {"backups": [msgspec.to_builtins(backup) for backup in backups]}
