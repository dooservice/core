"""DooServiceSDK — unified entry point for all services."""

from __future__ import annotations

import docker as docker_sdk

from dooservice_db_agent import ProxyConfigRepository, close_db, init_db
from dooservice_dns import DnsManager, create_dns_manager
from dooservice_docker import DockerClient
from dooservice_s3 import StorageClient

from .backup import BackupService, S3Backend
from .bootstrap import Bootstrap, PgDogConfig, PostgresProvisioning
from .config import Config
from .domains import DomainService
from .environments import EnvironmentService
from .git import GitService
from .projects import ProjectService
from .proxy import ProxyService


class DooServiceSDK:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._docker: DockerClient | None = None
        self._pgdog: PgDogConfig | None = None
        self._pg: PostgresProvisioning | None = None
        self._bootstrap: Bootstrap | None = None
        self._dns_manager: DnsManager | None = None

    @classmethod
    def from_env(cls) -> DooServiceSDK:
        return cls(Config.from_env())

    async def __aenter__(self) -> DooServiceSDK:
        await self._open()
        return self

    async def __aexit__(self, *_) -> None:
        await self._close()

    @property
    def bootstrap(self) -> Bootstrap:
        return self._bootstrap

    @property
    def projects(self) -> ProjectService:
        return ProjectService(self._config.projects_dir)

    @property
    def environments(self) -> EnvironmentService:
        return EnvironmentService(self._docker, self._pgdog, self._pg, self._dns_manager, self._config.projects_dir)

    @property
    def backups(self) -> BackupService:
        backend = None
        if self._config.s3.enabled:
            client = StorageClient(
                endpoint=self._config.s3.endpoint,
                access_key=self._config.s3.access_key,
                secret_key=self._config.s3.secret_key,
                bucket=self._config.s3.bucket,
                region=self._config.s3.region,
            )
            backend = S3Backend(client)
        return BackupService(self._docker, self._config.projects_dir, backend)

    @property
    def proxy(self) -> ProxyService:
        return ProxyService()

    @property
    def domains(self) -> DomainService:
        return DomainService(self._dns_manager)

    @property
    def git(self) -> GitService:
        return GitService(self._config.projects_dir)

    @property
    def docker(self) -> DockerClient:
        return self._docker

    @property
    def pgdog(self) -> PgDogConfig:
        return self._pgdog

    @property
    def config(self) -> Config:
        return self._config

    async def _open(self) -> None:
        self._config.db_path.parent.mkdir(parents=True, exist_ok=True)
        await init_db(f"sqlite://{self._config.db_path}")
        self._docker = DockerClient(docker_sdk.from_env())
        self._pgdog = PgDogConfig(
            self._docker,
            self._config.pgdog_config_dir,
            default_pool_size=self._config.pgdog.default_pool_size,
            maintenance_pool_size=self._config.pgdog.maintenance_pool_size,
        )
        self._pg = PostgresProvisioning(self._docker)
        proxy_config = await ProxyConfigRepository.get_or_default()
        self._dns_manager = create_dns_manager(proxy_config.tls.dns_provider)
        self._bootstrap = Bootstrap(self._docker, self._config, proxy_config, self._dns_manager)

    async def _close(self) -> None:
        if self._dns_manager:
            await self._dns_manager.close()
        if self._docker:
            self._docker.close()
        await close_db()
