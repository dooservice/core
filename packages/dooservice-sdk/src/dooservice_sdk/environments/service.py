from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import shutil
import uuid
from uuid import UUID

import httpx
from dooservice_db_agent import EnvironmentRepository, ProjectRepository, ProxyConfigRepository
from dooservice_dns import DnsManager, NoopDnsManager
from dooservice_docker import DockerClient
from dooservice_models import (
    CONTAINER_STOP_TIMEOUT_SECONDS,
    DOOSERVICE_NETWORK_NAME,
    ODOO_BACKUPS_DIR,
    ODOO_DATA_DIR,
    ODOO_IMAGE,
    SSL_READINESS_POLL_INTERVAL_SECONDS,
    SSL_READINESS_TIMEOUT_SECONDS,
    Environment,
    EnvironmentConfig,
    EnvironmentMode,
    Project,
    ProxyConfig,
    RuntimeState,
)

from ..bootstrap.pgdog import PgDogConfig
from ..bootstrap.postgres import PostgresProvisioning
from ..errors import CloneFailedError, DatabaseInitializationFailedError, NeutralizeFailedError
from . import odoo, odoo_conf

log = logging.getLogger(__name__)


class EnvironmentService:
    def __init__(
        self,
        docker: DockerClient,
        pgdog: PgDogConfig,
        pg: PostgresProvisioning,
        dns_manager: DnsManager | None = None,
        projects_dir: Path | None = None,
    ) -> None:
        self.docker = docker
        self.pgdog = pgdog
        self.pg = pg
        self.dns_manager = dns_manager or NoopDnsManager()
        self._projects_dir = projects_dir

    @staticmethod
    def build_environment(
        project: Project,
        mode: EnvironmentMode,
        *,
        environment_id: uuid.UUID | None = None,
        odoo_version: str | None = None,
        admin_email: str = "",
        admin_password: str = "",
        timezone: str | None = None,
        language: str | None = None,
        has_repository: bool = False,
        base_workers: int = 1,
    ) -> Environment:
        env_id = environment_id or uuid.uuid4()
        short = env_id.hex[:8]
        name = f"{project.name}-{mode.value}-{env_id.hex[:4]}"
        if mode == EnvironmentMode.PRODUCTION:
            name = project.name

        config_kwargs: dict = {
            "pg_db_name": f"db_{short}",
            "pg_db_user": f"usr_{short}",
            "pg_db_password": uuid.uuid4().hex,
            "admin_email": admin_email,
            "admin_password": admin_password,
            "base_workers": base_workers,
        }
        if timezone:
            config_kwargs["timezone"] = timezone
        if language:
            config_kwargs["language"] = language

        return Environment(
            id=env_id,
            project_id=project.id,
            name=name,
            mode=mode,
            odoo_version=odoo_version or project.odoo_version,
            has_repository=has_repository,
            config=EnvironmentConfig(**config_kwargs),
        )

    async def prepare_environment(
        self,
        project_name: str,
        mode: EnvironmentMode,
        *,
        environment_id: uuid.UUID | None = None,
        odoo_version: str | None = None,
        admin_email: str = "",
        admin_password: str = "",
        timezone: str | None = None,
        language: str | None = None,
        has_repository: bool | None = None,
        base_workers: int = 1,
    ) -> Environment:
        project = await ProjectRepository.get_by_name(project_name)
        return self.build_environment(
            project, mode,
            environment_id=environment_id,
            odoo_version=odoo_version,
            admin_email=admin_email,
            admin_password=admin_password,
            timezone=timezone,
            language=language,
            has_repository=has_repository if has_repository is not None else project.has_repository,
            base_workers=base_workers,
        )

    async def configure_dns(self, environment: Environment, base_domain: str = "") -> tuple[Environment, ProxyConfig]:
        proxy = await ProxyConfigRepository.get_or_default()
        environment.config.primary_domain = proxy.primary_domain_for(environment.name, base_domain)
        environment.config.proxy_network_name = proxy.network_name
        if environment.config.primary_domain and proxy.server_ip:
            await self.dns_manager.ensure_record(environment.config.primary_domain, proxy.server_ip)
        return environment, proxy

    async def provision_postgres(self, environment: Environment) -> None:
        await self.pg.provision_environment(
            environment.config.pg_db_user,
            environment.config.pg_db_password,
        )

    async def configure_pooler(self, environment: Environment) -> None:
        total_workers = environment.config.base_workers + environment.config.extra_workers
        await self.pgdog.add_database(
            environment.config.pg_db_name,
            environment.config.pg_db_user,
            environment.config.pg_db_password,
            workers=total_workers,
        )

    async def update_pooler_workers(self, environment: Environment) -> None:
        total_workers = environment.config.base_workers + environment.config.extra_workers
        await self.pgdog.update_pool_size(
            environment.config.pg_db_name,
            environment.config.pg_db_user,
            total_workers,
        )

    async def initialize_database(self, environment: Environment, proxy_config: ProxyConfig) -> None:
        spec = odoo.build_spec(environment, tls_enabled=proxy_config.tls.enabled)
        init_result = await self.docker.run_ephemeral(
            image=spec.image,
            command=odoo.build_db_init_command(environment),
            network=spec.network,
            volumes=spec.volumes,
        )
        if init_result.exit_code != 0:
            raise DatabaseInitializationFailedError(init_result.exit_code, init_result.output.strip())

    async def create_container(self, environment: Environment, proxy_config: ProxyConfig) -> Environment:
        addons_dir: Path | None = None
        config_dir: Path | None = None

        if self._projects_dir is not None:
            try:
                project = await ProjectRepository.get_by_id(environment.project_id)
                env_root = self._projects_dir / project.name / environment.name
                config_dir = env_root / "config"
                conf_path = config_dir / "odoo.conf"
                if project.has_repository:
                    addons_dir = env_root / "addons"
                    addons_dir.mkdir(parents=True, exist_ok=True)
                existing_addons = odoo_conf.read_addons_path(conf_path)
                odoo_conf.write(conf_path, environment, addons_paths=existing_addons)
            except Exception:
                log.warning("Could not write odoo.conf for env %s", environment.id, exc_info=True)
                config_dir = None
                addons_dir = None

        spec = odoo.build_spec(
            environment,
            tls_enabled=proxy_config.tls.enabled,
            addons_dir=addons_dir,
            config_dir=config_dir,
        )
        environment.container_id = await self.docker.create_container(spec)
        return environment

    async def start_container(self, environment: Environment) -> None:
        await self.docker.start_container(environment.container_id)

    async def wait_for_ssl(self, environment: Environment, proxy_config: ProxyConfig) -> None:
        if not proxy_config.tls.enabled or not environment.config.primary_domain:
            return
        domain = environment.config.primary_domain
        deadline = asyncio.get_running_loop().time() + SSL_READINESS_TIMEOUT_SECONDS
        while asyncio.get_running_loop().time() < deadline:
            if await self._health_check_passes(domain):
                return
            await asyncio.sleep(SSL_READINESS_POLL_INTERVAL_SECONDS)
        log.warning("Instance at %s not ready after %ds; continuing", domain, SSL_READINESS_TIMEOUT_SECONDS)

    @staticmethod
    async def _health_check_passes(domain: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"https://{domain}/web/health")
                return response.json().get("status") == "pass"
        except Exception:
            return False

    async def save_environment(self, environment: Environment) -> Environment:
        environment.start()
        await EnvironmentRepository.save(environment)
        return environment

    async def prepare_clone(
        self,
        source_id: UUID,
        mode: EnvironmentMode,
        *,
        environment_id: UUID | None = None,
    ) -> tuple[Environment, Environment]:
        source  = await EnvironmentRepository.get(source_id)
        project = await ProjectRepository.get_by_id(source.project_id)
        target  = self.build_environment(
            project, mode,
            environment_id=environment_id,
            has_repository=project.has_repository,
            base_workers=source.config.base_workers,
        )
        return target, source

    async def dump_environment_data(
        self,
        source: Environment,
        projects_dir: Path,
    ) -> tuple[Path, str]:
        project  = await ProjectRepository.get_by_id(source.project_id)
        temp_dir = projects_dir / project.name / source.name / "backups"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_filename = f"clone_{uuid.uuid4().hex[:8]}.zip"
        container_path = f"{ODOO_BACKUPS_DIR}/{temp_filename}"
        dump_result = await self.docker.run_ephemeral(
            image=f"{ODOO_IMAGE}:{source.odoo_version}",
            command=odoo.build_dump_cmd(source, container_path),
            network=DOOSERVICE_NETWORK_NAME,
            volumes={
                f"odoo_data_{source.id.hex}": ODOO_DATA_DIR,
                str(temp_dir): ODOO_BACKUPS_DIR,
            },
        )
        if dump_result.exit_code != 0:
            raise CloneFailedError("dump", dump_result.output.strip())
        return temp_dir, temp_filename

    async def load_environment_data(
        self,
        target: Environment,
        temp_dir: Path,
        temp_filename: str,
        *,
        neutralize: bool = True,
    ) -> None:
        container_path = f"{ODOO_BACKUPS_DIR}/{temp_filename}"
        load_result = await self.docker.run_ephemeral(
            image=f"{ODOO_IMAGE}:{target.odoo_version}",
            command=odoo.build_load_cmd(target, container_path, neutralize=neutralize),
            network=DOOSERVICE_NETWORK_NAME,
            volumes={
                f"odoo_data_{target.id.hex}": ODOO_DATA_DIR,
                str(temp_dir): ODOO_BACKUPS_DIR,
            },
        )
        (temp_dir / temp_filename).unlink(missing_ok=True)
        if load_result.exit_code != 0:
            raise CloneFailedError("load", load_result.output.strip())

    async def neutralize_database(self, environment: Environment) -> None:
        config_dir: str | None = None
        if self._projects_dir is not None:
            project = await ProjectRepository.get_by_id(environment.project_id)
            config_dir = str(self._projects_dir / project.name / environment.name / "config")

        volumes: dict[str, str] = {f"odoo_data_{environment.id.hex}": ODOO_DATA_DIR}
        if config_dir is not None:
            volumes[config_dir] = odoo.ODOO_CONFIG_DIR

        result = await self.docker.run_ephemeral(
            image=f"{ODOO_IMAGE}:{environment.odoo_version}",
            command=odoo.build_db_neutralize_cmd(environment),
            network=DOOSERVICE_NETWORK_NAME,
            volumes=volumes,
        )
        if result.exit_code != 0:
            raise NeutralizeFailedError("neutralize", result.output.strip())

    async def provision(
        self,
        project_name: str,
        mode: EnvironmentMode,
        *,
        odoo_version: str | None = None,
        admin_email: str = "",
        admin_password: str = "",
        timezone: str | None = None,
        language: str | None = None,
    ) -> Environment:
        env = await self.prepare_environment(
            project_name, mode,
            odoo_version=odoo_version,
            admin_email=admin_email,
            admin_password=admin_password,
            timezone=timezone,
            language=language,
        )
        env, proxy = await self.configure_dns(env)
        await self.provision_postgres(env)
        await self.configure_pooler(env)
        await self.initialize_database(env, proxy)
        env = await self.create_container(env, proxy)
        await self.start_container(env)
        return await self.save_environment(env)

    async def start(self, environment_id: UUID) -> Environment:
        env = await self.get(environment_id)
        await self.docker.start_container(env.container_id)
        env.start()
        await EnvironmentRepository.update_runtime_state(env.id, env.runtime_state)
        return env

    async def stop(self, environment_id: UUID) -> Environment:
        env = await self.get(environment_id)
        await self.docker.stop_container(env.container_id, timeout=CONTAINER_STOP_TIMEOUT_SECONDS)
        env.stop()
        await EnvironmentRepository.update_runtime_state(env.id, env.runtime_state)
        return env

    async def clone(
        self,
        source_id: UUID,
        *,
        mode: EnvironmentMode = EnvironmentMode.DEVELOPMENT,
        projects_dir: Path,
    ) -> Environment:
        target, source = await self.prepare_clone(source_id, mode)
        target, proxy  = await self.configure_dns(target)
        await self.provision_postgres(target)
        await self.configure_pooler(target)
        temp_dir, temp_filename = await self.dump_environment_data(source, projects_dir)
        await self.load_environment_data(target, temp_dir, temp_filename)
        target = await self.create_container(target, proxy)
        await self.start_container(target)
        return await self.save_environment(target)

    async def deprovision_postgres(self, environment: Environment) -> None:
        await self.pg.deprovision_environment(environment.config.pg_db_name, environment.config.pg_db_user)

    async def remove_pooler(self, environment: Environment) -> None:
        await self.pgdog.remove_database(environment.config.pg_db_name, environment.config.pg_db_user)

    async def update_routing(self, environment_id: UUID) -> Environment:
        environment = await EnvironmentRepository.get(environment_id)
        proxy_config = await ProxyConfigRepository.get_or_default()
        await EnvironmentRepository.update_runtime_state(environment_id, RuntimeState.PROVISIONING)
        try:
            await self.docker.stop_container(environment.container_id, timeout=CONTAINER_STOP_TIMEOUT_SECONDS)
            await self.docker.remove_container(environment.container_id)
            environment = await self.create_container(environment, proxy_config)
            await self.start_container(environment)
            await EnvironmentRepository.update_container_id(environment.id, environment.container_id)
            await EnvironmentRepository.update_runtime_state(environment_id, RuntimeState.RUNNING)
            return environment
        except Exception:
            await EnvironmentRepository.update_runtime_state(environment_id, RuntimeState.FAILED)
            raise

    async def get(self, environment_id: UUID) -> Environment:
        return await EnvironmentRepository.get(environment_id)

    async def list(self, project_name: str) -> list[Environment]:
        project = await ProjectRepository.get_by_name(project_name)
        return await EnvironmentRepository.list_for_project(project.id)

    async def delete(self, environment_id: UUID) -> None:
        env = await self.get(environment_id)
        if env.config.primary_domain:
            await self.dns_manager.remove_record(env.config.primary_domain)
        if env.config.custom_domain:
            await self.dns_manager.remove_record(env.config.custom_domain.domain)
        if env.container_id:
            await self.docker.remove_container(env.container_id, force=True)
        await self.docker.remove_volume(f"odoo_data_{env.id.hex}")
        await self.pgdog.remove_database(env.config.pg_db_name, env.config.pg_db_user)
        await self.pg.deprovision_environment(env.config.pg_db_name, env.config.pg_db_user)
        await EnvironmentRepository.delete(env.id)
        if self._projects_dir is not None:
            project = await ProjectRepository.get_by_id(env.project_id)
            env_dir = self._projects_dir / project.name / env.name
            if env_dir.exists():
                shutil.rmtree(env_dir)
