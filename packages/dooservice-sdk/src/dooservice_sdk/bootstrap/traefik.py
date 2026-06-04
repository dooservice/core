"""Traefik proxy container lifecycle manager."""

from __future__ import annotations

from pathlib import Path

from docker.errors import NotFound

from dooservice_docker import DockerClient
from dooservice_models import (
    TRAEFIK_HTTP_PORT,
    TRAEFIK_HTTPS_PORT,
    TRAEFIK_IMAGE,
    ContainerSpec,
    ContainerState,
    ProxyConfig,
    ProxyStatus,
    RestartPolicy,
)

from ..proxy.labels import ACME_HTTP_RESOLVER, ACME_RESOLVER
from ..proxy.traefik import TraefikDnsProvider


class TraefikProxyService:
    def __init__(
        self,
        docker: DockerClient,
        proxy_config: ProxyConfig,
        letsencrypt_dir: Path,
    ) -> None:
        self.docker = docker
        self.proxy_config = proxy_config
        self.letsencrypt_dir = letsencrypt_dir

    def build_spec(self) -> ContainerSpec:
        config = self.proxy_config
        return ContainerSpec(
            image=TRAEFIK_IMAGE,
            name=config.container_name,
            command=self.build_command(),
            env=self.build_env(),
            ports={TRAEFIK_HTTP_PORT: config.http_port, TRAEFIK_HTTPS_PORT: config.https_port},
            volumes={
                "/var/run/docker.sock": "/var/run/docker.sock",
                str(self.letsencrypt_dir): "/letsencrypt",
            },
            labels=self.build_labels(),
            network=config.network_name,
            restart_policy=RestartPolicy.UNLESS_STOPPED,
        )

    def build_command(self) -> list[str]:
        config = self.proxy_config
        command = [
            "--providers.docker=true",
            "--providers.docker.exposedbydefault=false",
            f"--providers.docker.network={config.network_name}",
            f"--entrypoints.web.address=:{TRAEFIK_HTTP_PORT}",
            f"--entrypoints.websecure.address=:{TRAEFIK_HTTPS_PORT}",
            "--entrypoints.websecure.transport.respondingTimeouts.readTimeout=300s",
            "--entrypoints.websecure.transport.respondingTimeouts.writeTimeout=300s",
            "--entrypoints.websecure.transport.respondingTimeouts.idleTimeout=180s",
            "--serversTransport.forwardingTimeouts.dialTimeout=30s",
            "--serversTransport.forwardingTimeouts.responseHeaderTimeout=300s",
            "--serversTransport.forwardingTimeouts.idleConnTimeout=90s",
            "--log.level=INFO",
        ]
        tls = config.tls
        if tls.enabled:
            command += [
                "--entrypoints.web.http.redirections.entryPoint.to=websecure",
                "--entrypoints.web.http.redirections.entryPoint.scheme=https",
                "--entrypoints.web.http.redirections.entryPoint.permanent=true",
                f"--certificatesresolvers.{ACME_RESOLVER}.acme.email={tls.acme_email}",
                f"--certificatesresolvers.{ACME_RESOLVER}.acme.storage=/letsencrypt/acme.json",
            ]
            if tls.use_wildcard and tls.dns_provider:
                provider_name = TraefikDnsProvider.name(tls.dns_provider)
                command.append(f"--certificatesresolvers.{ACME_RESOLVER}.acme.dnschallenge.provider={provider_name}")
            else:
                command.append(f"--certificatesresolvers.{ACME_RESOLVER}.acme.httpchallenge.entrypoint=web")
            command += [
                f"--certificatesresolvers.{ACME_HTTP_RESOLVER}.acme.email={tls.acme_email}",
                f"--certificatesresolvers.{ACME_HTTP_RESOLVER}.acme.storage=/letsencrypt/acme-http.json",
                f"--certificatesresolvers.{ACME_HTTP_RESOLVER}.acme.httpchallenge.entrypoint=web",
            ]
            if tls.staging:
                staging_url = "https://acme-staging-v02.api.letsencrypt.org/directory"
                command += [
                    f"--certificatesresolvers.{ACME_RESOLVER}.acme.caserver={staging_url}",
                    f"--certificatesresolvers.{ACME_HTTP_RESOLVER}.acme.caserver={staging_url}",
                ]
        if config.dashboard_enabled:
            command += ["--api.dashboard=true", "--api.insecure=false"]
        return command

    def build_env(self) -> dict[str, str]:
        provider = self.proxy_config.tls.dns_provider
        if provider is None:
            return {}
        return TraefikDnsProvider.env_vars(provider)

    def build_labels(self) -> dict[str, str]:
        config = self.proxy_config
        labels: dict[str, str] = {"traefik.enable": "true"}
        if config.dashboard_enabled:
            host = config.dashboard_host()
            if host:
                labels.update(
                    {
                        "traefik.http.routers.dashboard.rule": f"Host(`{host}`)",
                        "traefik.http.routers.dashboard.entrypoints": "websecure",
                        "traefik.http.routers.dashboard.tls": "true",
                        "traefik.http.routers.dashboard.tls.certresolver": ACME_RESOLVER,
                        "traefik.http.routers.dashboard.service": "api@internal",
                    }
                )
        return labels

    def ensure_acme_storage(self) -> None:
        self.letsencrypt_dir.mkdir(parents=True, exist_ok=True)
        for filename in ("acme.json", "acme-http.json"):
            path = self.letsencrypt_dir / filename
            path.touch(exist_ok=True)
            path.chmod(0o600)

    async def ensure_running(self) -> None:
        await self.docker.ensure_network(self.proxy_config.network_name)
        self.ensure_acme_storage()
        try:
            info = await self.docker.inspect_container(self.proxy_config.container_name)
        except NotFound:
            spec = self.build_spec()
            await self.docker.pull_image(spec.image)
            container_id = await self.docker.create_container(spec)
            await self.docker.start_container(container_id)
            return
        if info.state != ContainerState.RUNNING:
            await self.docker.start_container(self.proxy_config.container_name)

    async def stop(self) -> None:
        await self.docker.stop_container(self.proxy_config.container_name)

    async def destroy(self) -> None:
        await self.docker.remove_container(self.proxy_config.container_name, force=True)

    async def status(self) -> ProxyStatus:
        try:
            info = await self.docker.inspect_container(self.proxy_config.container_name)
        except NotFound:
            return ProxyStatus(
                running=False,
                base_domain=self.proxy_config.base_domain,
                secondary_domains=self.proxy_config.secondary_domains,
            )
        return ProxyStatus(
            running=info.state == ContainerState.RUNNING,
            base_domain=self.proxy_config.base_domain,
            secondary_domains=self.proxy_config.secondary_domains,
            container_id=info.id,
            dashboard_domain=self.proxy_config.dashboard_host(),
        )
