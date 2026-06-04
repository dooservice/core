from __future__ import annotations

from docker.errors import NotFound

from dooservice_docker import DockerClient
from dooservice_models import (
    DOOSERVICE_NETWORK_NAME,
    POSTGRES_CONTAINER_NAME,
    POSTGRES_DATA_DIR,
    POSTGRES_IMAGE,
    POSTGRES_SUPERUSER,
    POSTGRES_VOLUME_NAME,
    ContainerSpec,
    ContainerState,
    Healthcheck,
    RestartPolicy,
)

from ..config import PostgresSettings
from .service_status import ServiceStatus


class SharedPostgresService:
    def __init__(
        self,
        docker: DockerClient,
        settings: PostgresSettings,
        network_name: str = DOOSERVICE_NETWORK_NAME,
    ) -> None:
        self.docker = docker
        self.settings = settings
        self.network_name = network_name

    def _pg_args(self) -> list[str]:
        pg = self.settings
        params: dict[str, str] = {
            "max_connections":                     str(pg.max_connections),
            "shared_buffers":                      pg.shared_buffers,
            "effective_cache_size":                pg.effective_cache_size,
            "work_mem":                            pg.work_mem,
            "maintenance_work_mem":                pg.maintenance_work_mem,
            "random_page_cost":                    pg.random_page_cost,
            "effective_io_concurrency":            str(pg.effective_io_concurrency),
            "wal_compression":                     pg.wal_compression,
            "checkpoint_completion_target":        pg.checkpoint_completion_target,
            "max_wal_size":                        pg.max_wal_size,
            "min_wal_size":                        pg.min_wal_size,
            "autovacuum_max_workers":              str(pg.autovacuum_max_workers),
            "autovacuum_naptime":                  pg.autovacuum_naptime,
            "autovacuum_vacuum_scale_factor":      pg.autovacuum_vacuum_scale_factor,
            "tcp_keepalives_idle":                 str(pg.tcp_keepalives_idle),
            "tcp_keepalives_interval":             str(pg.tcp_keepalives_interval),
            "tcp_keepalives_count":                str(pg.tcp_keepalives_count),
            "idle_in_transaction_session_timeout": pg.idle_in_transaction_session_timeout,
            "idle_session_timeout":                pg.idle_session_timeout,
            "statement_timeout":                   pg.statement_timeout,
            "password_encryption":                 "md5",
        }
        args = ["postgres"]
        for key, value in params.items():
            args += ["-c", f"{key}={value}"]
        return args

    def build_spec(self) -> ContainerSpec:
        return ContainerSpec(
            image=POSTGRES_IMAGE,
            name=POSTGRES_CONTAINER_NAME,
            env={
                "POSTGRES_USER":     POSTGRES_SUPERUSER,
                "POSTGRES_PASSWORD": self.settings.superuser_password,
                "POSTGRES_DB":       "postgres",
            },
            command=self._pg_args(),
            volumes={POSTGRES_VOLUME_NAME: POSTGRES_DATA_DIR},
            network=self.network_name,
            healthcheck=Healthcheck(
                test=["CMD-SHELL", f"pg_isready -U {POSTGRES_SUPERUSER} -d postgres"],
                interval_seconds=2,
                timeout_seconds=2,
                retries=15,
                start_period_seconds=3,
            ),
            restart_policy=RestartPolicy.UNLESS_STOPPED,
        )

    async def ensure_running(self) -> None:
        await self.docker.ensure_network(self.network_name)
        try:
            info = await self.docker.inspect_container(POSTGRES_CONTAINER_NAME)
        except NotFound:
            spec = self.build_spec()
            await self.docker.pull_image(spec.image)
            container_id = await self.docker.create_container(spec)
            await self.docker.start_container(container_id)
            return
        if info.state != ContainerState.RUNNING:
            await self.docker.start_container(POSTGRES_CONTAINER_NAME)

    async def stop(self) -> None:
        await self.docker.stop_container(POSTGRES_CONTAINER_NAME)

    async def destroy(self) -> None:
        await self.docker.remove_container(POSTGRES_CONTAINER_NAME, force=True)

    async def status(self) -> ServiceStatus:
        try:
            info = await self.docker.inspect_container(POSTGRES_CONTAINER_NAME)
        except NotFound:
            return ServiceStatus(name="postgres", running=False)
        return ServiceStatus(name="postgres", running=info.state == ContainerState.RUNNING, container_id=info.id)


class PostgresProvisioning:
    def __init__(self, docker: DockerClient) -> None:
        self._docker = docker

    async def provision_environment(self, role: str, password: str) -> None:
        await self._sql(f"CREATE ROLE {role} WITH LOGIN CREATEDB PASSWORD '{password}'")

    async def deprovision_environment(self, database: str, role: str) -> None:
        await self._sql(
            f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            f"WHERE datname = '{database}' AND pid <> pg_backend_pid()"
        )
        await self._sql(f"DROP DATABASE IF EXISTS {database}")
        await self._sql(f"DROP ROLE IF EXISTS {role}")

    async def _sql(self, statement: str) -> None:
        result = await self._docker.run_command(
            POSTGRES_CONTAINER_NAME,
            ["psql", "-U", POSTGRES_SUPERUSER, "-d", "postgres", "-c", statement],
        )
        if result.exit_code != 0:
            raise RuntimeError(f"psql error in {POSTGRES_CONTAINER_NAME}: {result.output.strip()}")
