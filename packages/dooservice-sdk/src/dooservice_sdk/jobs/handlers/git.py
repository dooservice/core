from __future__ import annotations

import uuid
from uuid import UUID

import msgspec

from dooservice_db_agent import DeploymentRepository, EnvironmentRepository, ProjectRepository
from dooservice_models import BackupSource, BackupType, DeploymentStatus, EnvironmentDeployment
from dooservice_protocol import GitPullArgs, ProjectKeySetupArgs, SubmoduleKeyDeleteArgs, SubmoduleKeySetupArgs

from ...environments import odoo_conf
from ...git import addons
from ..context import JobContext


class ProjectKeySetup:
    async def run(self, ctx: JobContext) -> dict:
        args   = msgspec.convert(ctx.args, ProjectKeySetupArgs)
        result = ctx.sdk.git.setup_project_key(args.project_name)
        return {"public_key": result["public_key"]}


class SubmoduleKeySetup:
    async def run(self, ctx: JobContext) -> dict:
        args   = msgspec.convert(ctx.args, SubmoduleKeySetupArgs)
        result = ctx.sdk.git.setup_submodule_key(args.project_name, args.repo_url)
        return {"public_key": result["public_key"]}


class SubmoduleKeyDelete:
    async def run(self, ctx: JobContext) -> dict:
        args = msgspec.convert(ctx.args, SubmoduleKeyDeleteArgs)
        ctx.sdk.git.delete_submodule_key(args.project_name, args.repo_url)
        return {"deleted": True}


class GitPull:
    async def run(self, ctx: JobContext) -> dict:
        args    = msgspec.convert(ctx.args, GitPullArgs)
        env_id  = UUID(args.environment_id)
        env     = await EnvironmentRepository.get(env_id)
        project = await ProjectRepository.get_by_id(env.project_id)
        branch  = args.branch or env.branch

        await ctx.progress("Creating pre-deploy backup", 0)
        commit_short = (env.commit or "")[:7] or "—"
        backup = await ctx.sdk.backups.create(
            env, project.name,
            backup_type=BackupType.DATABASE,
            description=f"pre-deploy · {branch or '?'} @ {commit_short}",
            source=BackupSource.PRE_DEPLOY,
        )

        revision   = await DeploymentRepository.next_revision(env_id)
        deployment = EnvironmentDeployment(
            id=uuid.uuid4(),
            environment_id=env_id,
            revision=revision,
            triggered_by="git.pull",
            commit_before=env.commit,
            commit_after=None,
            branch=branch,
            config_snapshot=msgspec.to_builtins(env.config),
            backup_id=backup.id,
            status=DeploymentStatus.SUCCESS,
        )
        await DeploymentRepository.save(deployment)

        try:
            await ctx.progress("Pulling latest changes", 20)
            new_commit = await ctx.sdk.git.pull(project.name, env.name, branch=branch)

            await ctx.progress("Updating Odoo config", 65)
            env_root  = ctx.sdk.config.projects_dir / project.name / env.name
            new_paths = addons.scan(env_root / "addons")
            old_paths = odoo_conf.read_addons_path(env_root / "config" / "odoo.conf")
            odoo_conf.write(env_root / "config" / "odoo.conf", env, new_paths)

            await ctx.progress("Restarting container", 85)
            if env.container_id:
                await ctx.sdk.docker.restart_container(env.container_id)

            await EnvironmentRepository.update_git(env_id, branch=branch, commit=new_commit)
            await DeploymentRepository.update_status(
                deployment.id, DeploymentStatus.SUCCESS, commit_after=new_commit,
            )
            await DeploymentRepository.drop_previous(env_id, revision)
            return {
                "commit": new_commit,
                "addons_changed": new_paths != old_paths,
                "deployment_id": str(deployment.id),
                "revision": revision,
            }

        except Exception:
            await DeploymentRepository.update_status(deployment.id, DeploymentStatus.FAILED)
            raise
