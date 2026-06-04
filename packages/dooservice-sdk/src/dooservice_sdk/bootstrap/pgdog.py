"""PgDog lifecycle service and runtime config manager."""

from __future__ import annotations

from pathlib import Path

from docker.errors import NotFound
from tomlkit import aot, document, dumps, parse, table

from dooservice_docker import DockerClient
from dooservice_models import (
    DOOSERVICE_NETWORK_NAME,
    PGDOG_CONFIG_DIR,
    PGDOG_CONTAINER_NAME,
    PGDOG_DEFAULT_POOL_SIZE,
    PGDOG_IMAGE,
    PGDOG_PORT,
    POSTGRES_CONTAINER_NAME,
    POSTGRES_PORT,
    ContainerSpec,
    ContainerState,
    Healthcheck,
    RestartPolicy,
)

from ..config import PgDogSettings
from .service_status import ServiceStatus


class PgDogService:
    def __init__(
        self,
        docker: DockerClient,
        config_dir: Path,
        settings: PgDogSettings,
        network_name: str = DOOSERVICE_NETWORK_NAME,
    ) -> None:
        self.docker      = docker
        self.config_dir  = config_dir
        self.settings    = settings
        self.network_name = network_name

    def build_spec(self) -> ContainerSpec:
        return ContainerSpec(
            image=PGDOG_IMAGE,
            name=PGDOG_CONTAINER_NAME,
            volumes={str(self.config_dir): PGDOG_CONFIG_DIR},
            network=self.network_name,
            working_dir=PGDOG_CONFIG_DIR,
            healthcheck=Healthcheck(
                test=["CMD-SHELL", f"nc -z 127.0.0.1 {PGDOG_PORT}"],
                interval_seconds=2,
                timeout_seconds=2,
                retries=15,
                start_period_seconds=3,
            ),
            restart_policy=RestartPolicy.UNLESS_STOPPED,
        )

    def write_initial_config(self) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        pgdog_toml = self.config_dir / "pgdog.toml"
        users_toml = self.config_dir / "users.toml"
        if not pgdog_toml.exists():
            pg = self.settings
            pgdog_toml.write_text(
                f'[general]\n'
                f'host = "0.0.0.0"\n'
                f'port = {PGDOG_PORT}\n'
                f'workers = {pg.workers}\n'
                f'pooler_mode = "{pg.pooler_mode}"\n'
                f'default_pool_size = {pg.default_pool_size}\n'
                f'min_pool_size = {pg.min_pool_size}\n'
                f'auth_type = "md5"\n'
                f'connect_timeout = {pg.connect_timeout}\n'
                f'checkout_timeout = {pg.checkout_timeout}\n'
                f'idle_timeout = {pg.idle_timeout}\n'
                f'server_lifetime = {pg.server_lifetime}\n'
            )
        if not users_toml.exists():
            users_toml.write_text("")

    async def ensure_running(self) -> None:
        await self.docker.ensure_network(self.network_name)
        self.write_initial_config()
        try:
            info = await self.docker.inspect_container(PGDOG_CONTAINER_NAME)
        except NotFound:
            spec = self.build_spec()
            await self.docker.pull_image(spec.image)
            container_id = await self.docker.create_container(spec)
            await self.docker.start_container(container_id)
            return
        if info.state != ContainerState.RUNNING:
            await self.docker.start_container(PGDOG_CONTAINER_NAME)

    async def stop(self) -> None:
        await self.docker.stop_container(PGDOG_CONTAINER_NAME)

    async def destroy(self) -> None:
        await self.docker.remove_container(PGDOG_CONTAINER_NAME, force=True)

    async def status(self) -> ServiceStatus:
        try:
            info = await self.docker.inspect_container(PGDOG_CONTAINER_NAME)
        except NotFound:
            return ServiceStatus(name="pgdog", running=False)
        return ServiceStatus(name="pgdog", running=info.state == ContainerState.RUNNING, container_id=info.id)


class PgDogConfig:
    def __init__(
        self,
        docker: DockerClient,
        config_dir: Path,
        backend_host: str = POSTGRES_CONTAINER_NAME,
        backend_port: int = POSTGRES_PORT,
        default_pool_size: int = PGDOG_DEFAULT_POOL_SIZE,
        maintenance_pool_size: int = 20,
    ) -> None:
        self.docker               = docker
        self.config_dir           = config_dir
        self.backend_host         = backend_host
        self.backend_port         = backend_port
        self.default_pool_size    = default_pool_size
        self.maintenance_pool_size = maintenance_pool_size
        self._pgdog_toml = config_dir / "pgdog.toml"
        self._users_toml = config_dir / "users.toml"

    @staticmethod
    def _load(path: Path):
        return parse(path.read_text()) if path.exists() else document()

    @staticmethod
    def _save(path: Path, data) -> None:
        path.write_text(dumps(data))

    def pool_size_for_workers(self, workers: int) -> int:
        """Calculate tenant DB pool_size from worker count.

        workers=0→12, workers=2→20, workers=4→36, workers=8→68
        """
        return max(self.default_pool_size, workers * 8 + 4)

    def set_user_pool_size(self, users_doc, user: str, db_name: str, pool_size: int) -> None:
        for entry in self._aot(users_doc, "users"):
            if entry.get("name") == user and entry.get("database") == db_name:
                entry["pool_size"] = pool_size
                return

    async def add_database(self, database: str, user: str, password: str, workers: int = 1) -> None:
        tenant_pool = self.pool_size_for_workers(workers)

        config = self._load(self._pgdog_toml)
        databases = self._aot(config, "databases")
        existing_db_names = {item.get("name") for item in databases}
        for db_name in (database, "postgres"):
            if db_name in existing_db_names:
                continue
            entry = table()
            entry["name"] = db_name
            entry["host"] = self.backend_host
            entry["port"] = self.backend_port
            databases.append(entry)
        users = self._load(self._users_toml)
        user_entries = self._aot(users, "users")
        existing_user_keys = {(item.get("name"), item.get("database")) for item in user_entries}
        for db_name in (database, "postgres"):
            pool = tenant_pool if db_name == database else self.maintenance_pool_size
            if (user, db_name) in existing_user_keys:
                self.set_user_pool_size(users, user, db_name, pool)
                continue
            entry = table()
            entry["name"]      = user
            entry["database"]  = db_name
            entry["password"]  = password
            entry["pool_size"] = pool
            user_entries.append(entry)
        self._save(self._users_toml, users)
        self._save(self._pgdog_toml, config)
        await self._reload()

    async def remove_database(self, database: str, user: str) -> None:
        config = self._load(self._pgdog_toml)
        kept_dbs = [item for item in self._aot(config, "databases") if item.get("name") != database]
        config["databases"] = aot()
        for item in kept_dbs:
            config["databases"].append(item)

        users = self._load(self._users_toml)
        kept_users = [
            item
            for item in self._aot(users, "users")
            if not (item.get("name") == user and item.get("database") in (database, "postgres"))
        ]
        users["users"] = aot()
        for item in kept_users:
            users["users"].append(item)
        self._save(self._users_toml, users)
        self._save(self._pgdog_toml, config)
        await self._reload()

    async def update_pool_size(self, database: str, user: str, workers: int) -> None:
        """Recalculate and apply pool_size after a worker count change."""
        tenant_pool = self.pool_size_for_workers(workers)
        users = self._load(self._users_toml)
        self.set_user_pool_size(users, user, database, tenant_pool)
        self.set_user_pool_size(users, user, "postgres", self.maintenance_pool_size)
        self._save(self._users_toml, users)
        await self._reload()

    @staticmethod
    def _aot(doc, key: str):
        if key not in doc:
            doc[key] = aot()
        return doc[key]

    async def _reload(self) -> None:
        try:
            await self.docker.run_command(PGDOG_CONTAINER_NAME, ["kill", "-HUP", "1"])
        except NotFound:
            return
