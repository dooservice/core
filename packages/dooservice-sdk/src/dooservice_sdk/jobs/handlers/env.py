from __future__ import annotations

import logging
from uuid import UUID

import msgspec

from dooservice_db_agent import EnvironmentRepository, ProjectRepository, ProxyConfigRepository
from dooservice_models import CONTAINER_STOP_TIMEOUT_SECONDS, Environment, EnvironmentMode, RuntimeState
from dooservice_protocol import (
    EnvCloneArgs,
    EnvDeleteArgs,
    EnvProvisionArgs,
    EnvRebuildArgs,
    EnvStartArgs,
    EnvStopArgs,
    WorkersUpdateArgs,
)

from ...environments import odoo_conf
from ...git import addons
from ..context import JobContext

log = logging.getLogger(__name__)


class ProvisionSupport:
    @staticmethod
    async def cleanup_failed_provision(ctx: JobContext, env: Environment) -> None:
        try:
            if env.container_id:
                await ctx.sdk.docker.remove_container(env.container_id, force=True)
            await ctx.sdk.environments.remove_pooler(env)
            await ctx.sdk.environments.deprovision_postgres(env)
        except Exception:
            log.warning("Cleanup incomplete after provision failure for env %s", env.id, exc_info=True)

    @staticmethod
    async def run_infrastructure_steps(ctx: JobContext, env: Environment, base_domain: str = "") -> Environment:
        await ctx.progress("Configuring DNS record", 15)
        env, proxy = await ctx.sdk.environments.configure_dns(env, base_domain)
        await ctx.progress("Provisioning PostgreSQL", 25)
        await ctx.sdk.environments.provision_postgres(env)
        await ctx.progress("Configuring connection pooler", 40)
        await ctx.sdk.environments.configure_pooler(env)
        await ctx.progress("Initializing Odoo database", 55)
        await ctx.sdk.environments.initialize_database(env, proxy)
        await ctx.progress("Creating container", 68)
        env = await ctx.sdk.environments.create_container(env, proxy)
        await ctx.progress("Starting container", 78)
        await ctx.sdk.environments.start_container(env)
        await ctx.progress("Waiting for SSL certificate", 82)
        await ctx.sdk.environments.wait_for_ssl(env, proxy)
        return env

    @staticmethod
    async def clone_repo(ctx: JobContext, env: Environment, repo_full_name: str, branch: str) -> Environment:
        project  = await ProjectRepository.get_by_id(env.project_id)
        env_root = ctx.sdk.config.projects_dir / project.name / env.name
        repo_url = f"git@github.com:{repo_full_name}.git"
        commit   = await ctx.sdk.git.clone(project.name, env.name, repo_url, branch)
        env.branch = branch
        env.commit = commit
        odoo_conf.write(env_root / "config" / "odoo.conf", env, addons.scan(env_root / "addons"))
        if env.container_id:
            await ctx.sdk.docker.restart_container(env.container_id)
        return env


class EnvProvision:
    async def run(self, ctx: JobContext) -> dict:
        args = msgspec.convert(ctx.args, EnvProvisionArgs)
        await ctx.progress("Preparing configuration", 0)
        env  = await ctx.sdk.environments.prepare_environment(
            args.project_name,
            EnvironmentMode(args.mode),
            environment_id=args.environment_id,
            odoo_version=args.odoo_version,
            admin_email=args.admin_email,
            admin_password=args.admin_password,
            timezone=args.timezone,
            language=args.language,
            has_repository=args.has_repository,
        )
        try:
            env = await ProvisionSupport.run_infrastructure_steps(ctx, env, args.base_domain)
            if args.neutralize:
                await ctx.progress("Neutralizing database", 62)
                await ctx.sdk.environments.neutralize_database(env)
            if args.has_repository:
                await ctx.progress("Cloning repository", 85)
                env = await ProvisionSupport.clone_repo(ctx, env, args.repo_full_name, args.branch)
            await ctx.progress("Saving environment", 95)
            env = await ctx.sdk.environments.save_environment(env)
        except Exception:
            await ProvisionSupport.cleanup_failed_provision(ctx, env)
            raise
        if ctx.scheduler is not None:
            ctx.scheduler.register(env.id, env.project_id, env.config.timezone)
        return {"environment_id": str(env.id), "name": env.name}


class EnvClone:
    async def run(self, ctx: JobContext) -> dict:
        args = msgspec.convert(ctx.args, EnvCloneArgs)
        await ctx.progress("Preparing clone", 0)
        target_env, source_env = await ctx.sdk.environments.prepare_clone(
            UUID(args.source_environment_id),
            EnvironmentMode(args.mode),
            environment_id=args.environment_id,
        )
        try:
            await ctx.progress("Configuring DNS record", 10)
            target_env, proxy = await ctx.sdk.environments.configure_dns(target_env, args.base_domain)
            await ctx.progress("Provisioning PostgreSQL", 20)
            await ctx.sdk.environments.provision_postgres(target_env)
            await ctx.progress("Configuring connection pooler", 30)
            await ctx.sdk.environments.configure_pooler(target_env)
            await ctx.progress("Exporting source data", 40)
            temp_dir, temp_filename = await ctx.sdk.environments.dump_environment_data(
                source_env, ctx.sdk.config.projects_dir
            )
            await ctx.progress("Importing data", 55)
            await ctx.sdk.environments.load_environment_data(
                target_env, temp_dir, temp_filename, neutralize=args.neutralize
            )
            await ctx.progress("Creating container", 68)
            target_env = await ctx.sdk.environments.create_container(target_env, proxy)
            await ctx.progress("Starting container", 78)
            await ctx.sdk.environments.start_container(target_env)
            await ctx.progress("Waiting for SSL certificate", 82)
            await ctx.sdk.environments.wait_for_ssl(target_env, proxy)
            if target_env.has_repository:
                branch = args.branch or source_env.branch
                project = await ProjectRepository.get_by_id(source_env.project_id)
                await ctx.progress("Cloning repository", 88)
                target_env = await ProvisionSupport.clone_repo(ctx, target_env, project.repo_full_name, branch)
            await ctx.progress("Saving environment", 95)
            target_env = await ctx.sdk.environments.save_environment(target_env)
        except Exception:
            await ProvisionSupport.cleanup_failed_provision(ctx, target_env)
            raise
        if ctx.scheduler is not None:
            ctx.scheduler.register(target_env.id, target_env.project_id, target_env.config.timezone)
        return {"environment_id": str(target_env.id), "name": target_env.name}


class EnvRebuild:
    async def run(self, ctx: JobContext) -> dict:
        args   = msgspec.convert(ctx.args, EnvRebuildArgs)
        env_id = UUID(args.environment_id)

        env     = await EnvironmentRepository.get(env_id)
        project = await ProjectRepository.get_by_id(env.project_id)
        await EnvironmentRepository.update_runtime_state(env.id, RuntimeState.PROVISIONING)
        try:
            return await self._rebuild(ctx, env, project)
        except Exception:
            await EnvironmentRepository.update_runtime_state(env.id, RuntimeState.FAILED)
            raise

    async def _rebuild(self, ctx: JobContext, env: Environment, project) -> dict:
        await ctx.progress("Stopping container", 5)
        if env.container_id:
            await ctx.sdk.docker.stop_container(env.container_id, timeout=CONTAINER_STOP_TIMEOUT_SECONDS)
            await ctx.sdk.docker.remove_container(env.container_id, force=True)

        await ctx.progress("Dropping database", 20)
        await ctx.sdk.docker.remove_volume(f"odoo_data_{env.id.hex}")
        await ctx.sdk.environments.remove_pooler(env)
        await ctx.sdk.environments.deprovision_postgres(env)

        await ctx.progress("Re-provisioning PostgreSQL", 38)
        await ctx.sdk.environments.provision_postgres(env)

        await ctx.progress("Configuring connection pooler", 50)
        await ctx.sdk.environments.configure_pooler(env)

        proxy_config = await ProxyConfigRepository.get_or_default()

        await ctx.progress("Initializing Odoo database", 62)
        await ctx.sdk.environments.initialize_database(env, proxy_config)

        await ctx.progress("Creating container", 78)
        env = await ctx.sdk.environments.create_container(env, proxy_config)

        if env.has_repository and project.repo_full_name:
            await ctx.progress("Updating repository", 88)
            env_root   = ctx.sdk.config.projects_dir / project.name / env.name
            new_commit = await ctx.sdk.git.pull(project.name, env.name, branch=env.branch or "")
            env.commit = new_commit
            odoo_conf.write(env_root / "config" / "odoo.conf", env, addons.scan(env_root / "addons"))
            await EnvironmentRepository.update_git(env.id, branch=env.branch, commit=new_commit)

        await ctx.progress("Starting container", 94)
        await ctx.sdk.environments.start_container(env)

        await EnvironmentRepository.update_container_id(env.id, env.container_id)
        env.start()
        await EnvironmentRepository.update_runtime_state(env.id, env.runtime_state)
        return {"environment_id": str(env.id), "runtime_state": env.runtime_state.value}


class EnvStart:
    async def run(self, ctx: JobContext) -> dict:
        args = msgspec.convert(ctx.args, EnvStartArgs)
        env  = await ctx.sdk.environments.start(UUID(args.environment_id))
        return {"environment_id": str(env.id), "runtime_state": env.runtime_state.value}


class EnvStop:
    async def run(self, ctx: JobContext) -> dict:
        args = msgspec.convert(ctx.args, EnvStopArgs)
        env  = await ctx.sdk.environments.stop(UUID(args.environment_id))
        return {"environment_id": str(env.id), "runtime_state": env.runtime_state.value}


class EnvDelete:
    async def run(self, ctx: JobContext) -> dict:
        args   = msgspec.convert(ctx.args, EnvDeleteArgs)
        env_id = UUID(args.environment_id)
        if ctx.scheduler is not None:
            ctx.scheduler.unregister(env_id)
        await ctx.sdk.environments.delete(env_id)
        return {"deleted": True}


class WorkersUpdate:
    async def run(self, ctx: JobContext) -> dict:
        args   = msgspec.convert(ctx.args, WorkersUpdateArgs)
        env_id = UUID(args.environment_id)
        env    = await EnvironmentRepository.get(env_id)
        env.config.base_workers = args.workers
        await EnvironmentRepository.update_config(env_id, env.config)
        await ctx.sdk.environments.update_pooler_workers(env)
        await ctx.sdk.environments.update_routing(env_id)
        return {"workers": env.config.base_workers}
