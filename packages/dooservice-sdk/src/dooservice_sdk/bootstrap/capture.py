"""Capture screenshot service container lifecycle manager."""

from __future__ import annotations

import socket
from docker.errors import NotFound

from dooservice_docker import DockerClient
from dooservice_models import (
    CAPTURE_CONTAINER_NAME,
    CAPTURE_IMAGE,
    CAPTURE_PORT,
    ContainerSpec,
    ContainerState,
    RestartPolicy,
)

from ..proxy.labels import ACME_RESOLVER
from .service_status import ServiceStatus


class CaptureService:
    def __init__(
        self,
        docker: DockerClient,
        network_name: str,
        proxy_network_name: str,
        base_domain: str,
        api_secret: str,
        *,
        hostname: str = "",
        tls_enabled: bool = False,
    ) -> None:
        self.docker             = docker
        self.network_name       = network_name
        self.proxy_network_name = proxy_network_name
        self.base_domain        = base_domain
        self.api_secret         = api_secret
        self.tls_enabled        = tls_enabled
        self._hostname          = hostname

    @property
    def hostname(self) -> str:
        return self._hostname or socket.gethostname()

    @property
    def domain(self) -> str:
        return f"{self.hostname}.{self.base_domain}" if self.base_domain else ""

    def build_spec(self) -> ContainerSpec:
        return ContainerSpec(
            image=CAPTURE_IMAGE,
            name=CAPTURE_CONTAINER_NAME,
            env={"API_SECRET": self.api_secret, "GIN_MODE": "release"},
            volumes={"/etc/os-release": "/etc/os-release"},
            labels=self.build_labels(),
            network=self.network_name,
            restart_policy=RestartPolicy.UNLESS_STOPPED,
        )

    def build_labels(self) -> dict[str, str]:
        domain = self.domain
        if not domain:
            return {"traefik.enable": "false"}

        labels: dict[str, str] = {
            "traefik.enable": "true",
            "traefik.docker.network": self.proxy_network_name,
            f"traefik.http.services.capture-svc.loadbalancer.server.port": str(CAPTURE_PORT),
        }

        if self.tls_enabled:
            labels.update({
                "traefik.http.routers.capture.rule": f"Host(`{domain}`)",
                "traefik.http.routers.capture.entrypoints": "websecure",
                "traefik.http.routers.capture.tls": "true",
                "traefik.http.routers.capture.tls.certresolver": ACME_RESOLVER,
                "traefik.http.routers.capture.service": "capture-svc",
            })
        else:
            labels.update({
                "traefik.http.routers.capture.rule": f"Host(`{domain}`)",
                "traefik.http.routers.capture.entrypoints": "web",
                "traefik.http.routers.capture.service": "capture-svc",
            })

        return labels

    async def ensure_running(self) -> None:
        try:
            info = await self.docker.inspect_container(CAPTURE_CONTAINER_NAME)
        except NotFound:
            spec = self.build_spec()
            await self.docker.pull_image(spec.image)
            container_id = await self.docker.create_container(spec)
            await self.docker.start_container(container_id)
            return
        if info.state != ContainerState.RUNNING:
            await self.docker.start_container(CAPTURE_CONTAINER_NAME)

    async def stop(self) -> None:
        await self.docker.stop_container(CAPTURE_CONTAINER_NAME)

    async def destroy(self) -> None:
        await self.docker.remove_container(CAPTURE_CONTAINER_NAME, force=True)

    async def status(self) -> ServiceStatus:
        try:
            info = await self.docker.inspect_container(CAPTURE_CONTAINER_NAME)
        except NotFound:
            return ServiceStatus(name=CAPTURE_CONTAINER_NAME, running=False)
        return ServiceStatus(
            name=CAPTURE_CONTAINER_NAME,
            running=info.state == ContainerState.RUNNING,
            container_id=info.id,
        )
