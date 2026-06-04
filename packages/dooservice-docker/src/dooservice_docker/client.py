"""Docker daemon adapter — async wrapper over docker-py."""

from __future__ import annotations

import asyncio

import docker
from docker.errors import NotFound
from docker.models.containers import Container

from dooservice_models import (
    ContainerInfo,
    ContainerSpec,
    ContainerState,
    ExecResult,
)

from .payload import container_spec_to_kwargs


class DockerClient:
    def __init__(self, docker_client: docker.DockerClient | None = None) -> None:
        self.docker = docker_client or docker.from_env()

    async def pull_image(self, image: str) -> None:
        await asyncio.to_thread(self.docker.images.pull, image)

    async def create_container(self, spec: ContainerSpec) -> str:
        kwargs = container_spec_to_kwargs(spec)
        container = await asyncio.to_thread(self.docker.containers.create, **kwargs)
        return container.id

    async def start_container(self, container_id: str) -> None:
        container = await self.fetch_container(container_id)
        await asyncio.to_thread(container.start)

    async def stop_container(self, container_id: str, timeout: int = 10) -> None:
        """Idempotent: returns silently if the container does not exist."""
        try:
            container = await self.fetch_container(container_id)
        except NotFound:
            return
        await asyncio.to_thread(container.stop, timeout=timeout)

    async def restart_container(self, container_id: str, timeout: int = 10) -> None:
        container = await self.fetch_container(container_id)
        await asyncio.to_thread(container.restart, timeout=timeout)

    async def remove_container(self, container_id: str, force: bool = False) -> None:
        """Idempotent: returns silently if the container does not exist."""
        try:
            container = await self.fetch_container(container_id)
        except NotFound:
            return
        await asyncio.to_thread(container.remove, force=force, v=True)

    async def remove_volume(self, name: str) -> None:
        """Idempotent: returns silently if the volume does not exist."""
        try:
            volume = await asyncio.to_thread(self.docker.volumes.get, name)
            await asyncio.to_thread(volume.remove, force=True)
        except NotFound:
            pass

    async def run_command(self, container_id: str, command: list[str]) -> ExecResult:
        container = await self.fetch_container(container_id)
        result = await asyncio.to_thread(container.exec_run, command)
        return ExecResult(
            exit_code=result.exit_code,
            output=result.output.decode("utf-8", errors="replace"),
        )

    async def run_ephemeral(
        self,
        image: str,
        command: list[str],
        *,
        env: dict[str, str] | None = None,
        network: str | None = None,
        volumes: dict[str, str] | None = None,
    ) -> ExecResult:
        """Spawn a one-shot container, wait for it, return exit + logs, remove it."""
        volume_bindings = {source: {"bind": target, "mode": "rw"} for source, target in (volumes or {}).items()}
        container = await asyncio.to_thread(
            self.docker.containers.run,
            image,
            command=command,
            environment=env or {},
            network=network,
            volumes=volume_bindings or None,
            detach=True,
        )
        try:
            wait_result = await asyncio.to_thread(container.wait)
            logs = await asyncio.to_thread(container.logs)
            return ExecResult(
                exit_code=wait_result.get("StatusCode", -1),
                output=logs.decode("utf-8", errors="replace"),
            )
        finally:
            await asyncio.to_thread(container.remove, force=True, v=True)

    async def read_logs(self, container_id: str, tail: int = 100) -> str:
        container = await self.fetch_container(container_id)
        output = await asyncio.to_thread(container.logs, tail=tail)
        return output.decode("utf-8", errors="replace")

    async def fetch_container(self, container_id: str) -> Container:
        return await asyncio.to_thread(self.docker.containers.get, container_id)

    async def inspect_container(self, container_id: str) -> ContainerInfo:
        container = await self.fetch_container(container_id)
        return ContainerInfo(
            id=container.id,
            name=container.name,
            image=container.image.tags[0] if container.image and container.image.tags else "",
            state=ContainerState(container.status),
            status=container.status,
        )

    async def ensure_network(self, name: str) -> None:
        existing = await asyncio.to_thread(self.docker.networks.list, names=[name])
        if not existing:
            await asyncio.to_thread(self.docker.networks.create, name=name)

    async def remove_network(self, name: str) -> None:
        try:
            network = await asyncio.to_thread(self.docker.networks.get, name)
        except NotFound:
            return
        await asyncio.to_thread(network.remove)

    async def connect_container(self, network_name: str, container_id: str) -> None:
        network = await asyncio.to_thread(self.docker.networks.get, network_name)
        await asyncio.to_thread(network.connect, container_id)

    async def disconnect_container(self, network_name: str, container_id: str) -> None:
        network = await asyncio.to_thread(self.docker.networks.get, network_name)
        await asyncio.to_thread(network.disconnect, container_id)

    def close(self) -> None:
        self.docker.close()
