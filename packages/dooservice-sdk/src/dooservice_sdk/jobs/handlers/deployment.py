from __future__ import annotations

from uuid import UUID

import msgspec

from dooservice_db_agent import BackupRepository, DeploymentRepository, EnvironmentRepository, ProjectRepository
from dooservice_models import CONTAINER_STOP_TIMEOUT_SECONDS, DeploymentStatus, EnvironmentConfig, RuntimeState
from dooservice_protocol import EnvRollbackArgs, QueryDeploymentsArgs

from ...environments import odoo_conf
from ...git import addons
from ..context import JobContext


class EnvRollback:
    async def run(self, ctx: JobContext) -> dict:
        args       = msgspec.convert(ctx.args, EnvRollbackArgs)
        env_id     = UUID(args.environment_id)
        env        = await EnvironmentRepository.get(env_id)
        project    = await ProjectRepository.get_by_id(env.project_id)
        deployment = await DeploymentRepository.get_revision(env_id, args.revision)

        await EnvironmentRepository.update_runtime_state(env_id, RuntimeState.PROVISIONING)
        try:
            await ctx.progress("Stopping container", 5)
            if env.container_id:
                await ctx.sdk.docker.stop_container(
                    env.container_id, timeout=CONTAINER_STOP_TIMEOUT_SECONDS,
                )

            if deployment.backup_id is not None:
                await ctx.progress("Restoring database", 20)
                backup = await BackupRepository.get(deployment.backup_id)
                if backup is not None:
                    await ctx.sdk.backups.restore(backup, env)

            if deployment.commit_before is not None and env.has_repository:
                await ctx.progress("Reverting code", 60)
                env_root        = ctx.sdk.config.projects_dir / project.name / env.name
                restored_config = msgspec.convert(deployment.config_snapshot, EnvironmentConfig)
                await ctx.sdk.git.checkout(project.name, env.name, deployment.commit_before)
                env.config = restored_config
                env.commit = deployment.commit_before
                odoo_conf.write(env_root / "config" / "odoo.conf", env, addons.scan(env_root / "addons"))
                await EnvironmentRepository.update_git(
                    env_id, branch=deployment.branch, commit=deployment.commit_before,
                )
                await EnvironmentRepository.update_config(env_id, restored_config)

            await ctx.progress("Starting container", 85)
            await ctx.sdk.environments.start_container(env)

            await DeploymentRepository.update_status(deployment.id, DeploymentStatus.ROLLED_BACK)
            dropped_backup_ids = await DeploymentRepository.drop_after_revision(env_id, args.revision)
            for backup_id in dropped_backup_ids:
                await BackupRepository.mark_dropped(backup_id)

            await EnvironmentRepository.update_runtime_state(env_id, RuntimeState.RUNNING)
            return {"revision": args.revision, "commit": deployment.commit_before}
        except Exception:
            await EnvironmentRepository.update_runtime_state(env_id, RuntimeState.FAILED)
            raise


class QueryDeployments:
    async def run(self, ctx: JobContext) -> dict:
        args        = msgspec.convert(ctx.args, QueryDeploymentsArgs)
        deployments = await DeploymentRepository.list_for_environment(UUID(args.environment_id))
        return {"deployments": [msgspec.to_builtins(dep) for dep in deployments]}
