"""Traefik routing labels for Odoo environment containers (Traefik v3.6).

Two services (main + longpolling when workers >= 1), three shared
middlewares (headers, buffer, compress), and routers per domain (primary
+ optional verified custom domain).

Routing modes — switched by `tls_enabled`:
  - tls_enabled=False → HTTP-only routers on the `web` entrypoint, no
    TLS labels, no certresolver. Suitable for local dev or ProxyConfig
    with TLS disabled (no cert resolvers registered in Traefik).
  - tls_enabled=True  → only HTTPS routers on `websecure`. The HTTP
    → HTTPS redirect is handled at the `web` entrypoint level (see
    TraefikProxyService.build_command), so no per-router redirect
    middleware is needed. Primary domain → ACME_RESOLVER; custom
    domains → ACME_HTTP_RESOLVER (HTTP-01 only — wildcard certs
    cannot cover arbitrary third-party domains).
"""

from __future__ import annotations

from dooservice_models import CustomDomainStatus, Environment

ACME_RESOLVER = "letsencrypt"
ACME_HTTP_RESOLVER = "letsencrypt-http"

COMPRESSION_EXCLUDED_MIME = [
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/gif",
    "image/webp",
    "image/avif",
    "image/svg+xml",
    "video/mp4",
    "video/mpeg",
    "video/webm",
    "audio/mpeg",
    "audio/ogg",
    "audio/wav",
    "application/zip",
    "application/gzip",
    "application/x-gzip",
    "application/x-rar-compressed",
    "application/x-7z-compressed",
]


class OdooRoutingLabels:
    """Builds the full set of Traefik labels for an Odoo environment container."""

    def __init__(
        self,
        environment: Environment,
        proxy_network: str,
        *,
        tls_enabled: bool = False,
    ) -> None:
        self.environment = environment
        self.proxy_network = proxy_network
        self.tls_enabled = tls_enabled
        self.name = environment.name
        self.multi_worker = (environment.config.base_workers + environment.config.extra_workers) >= 1
        self.main_service = f"{self.name}-svc"
        self.longpolling_service = f"{self.name}-lp-svc" if self.multi_worker else None
        self.main_middlewares = f"{self.name}-headers,{self.name}-buffer,{self.name}-compress"
        self.static_middlewares = f"{self.name}-compress"

    def build(self) -> dict[str, str]:
        labels = self.base_labels()
        config = self.environment.config
        if config.primary_domain:
            labels.update(self.domain_router(self.name, config.primary_domain, ACME_RESOLVER))
            labels.update(self.static_router(f"{self.name}-static", config.primary_domain, ACME_RESOLVER))
        custom = config.custom_domain
        if custom is not None and custom.status == CustomDomainStatus.VERIFIED:
            labels.update(self.domain_router(f"{self.name}-cd", custom.domain, ACME_HTTP_RESOLVER))
            labels.update(self.static_router(f"{self.name}-cd-static", custom.domain, ACME_HTTP_RESOLVER))
        return labels

    def base_labels(self) -> dict[str, str]:
        name = self.name
        labels: dict[str, str] = {
            "traefik.enable": "true",
            "traefik.docker.network": self.proxy_network,
            f"traefik.http.services.{self.main_service}.loadbalancer.server.port": "8069",
            f"traefik.http.services.{self.main_service}.loadbalancer.responseForwarding.flushInterval": "100ms",
            f"traefik.http.middlewares.{name}-headers.headers.customrequestheaders.X-Forwarded-Proto": "https"
            if self.tls_enabled
            else "http",
            f"traefik.http.middlewares.{name}-buffer.buffering.maxRequestBodyBytes": "10485760",
            f"traefik.http.middlewares.{name}-buffer.buffering.maxResponseBodyBytes": "0",
            f"traefik.http.middlewares.{name}-compress.compress": "true",
            f"traefik.http.middlewares.{name}-compress.compress.excludedContentTypes": ",".join(
                COMPRESSION_EXCLUDED_MIME
            ),
        }
        if self.longpolling_service:
            labels[f"traefik.http.services.{self.longpolling_service}.loadbalancer.server.port"] = "8072"
        return labels

    def domain_router(self, prefix: str, domain: str, certresolver: str) -> dict[str, str]:
        host = f"Host(`{domain}`)"
        if self.tls_enabled:
            return self.tls_router(prefix, host, certresolver)
        return self.http_only_router(prefix, host)

    def tls_router(self, prefix: str, host: str, certresolver: str) -> dict[str, str]:
        labels = {
            f"traefik.http.routers.{prefix}.rule": host,
            f"traefik.http.routers.{prefix}.entrypoints": "websecure",
            f"traefik.http.routers.{prefix}.tls": "true",
            f"traefik.http.routers.{prefix}.tls.certresolver": certresolver,
            f"traefik.http.routers.{prefix}.service": self.main_service,
            f"traefik.http.routers.{prefix}.middlewares": self.main_middlewares,
        }
        if self.longpolling_service:
            longpolling_prefix = f"{prefix}-lp"
            labels.update(
                {
                    f"traefik.http.routers.{longpolling_prefix}.rule": f"{host} && (PathPrefix(`/websocket`) || PathPrefix(`/longpolling`))",
                    f"traefik.http.routers.{longpolling_prefix}.entrypoints": "websecure",
                    f"traefik.http.routers.{longpolling_prefix}.tls": "true",
                    f"traefik.http.routers.{longpolling_prefix}.tls.certresolver": certresolver,
                    f"traefik.http.routers.{longpolling_prefix}.service": self.longpolling_service,
                    f"traefik.http.routers.{longpolling_prefix}.priority": "200",
                }
            )
        return labels

    def http_only_router(self, prefix: str, host: str) -> dict[str, str]:
        labels = {
            f"traefik.http.routers.{prefix}.rule": host,
            f"traefik.http.routers.{prefix}.entrypoints": "web",
            f"traefik.http.routers.{prefix}.service": self.main_service,
            f"traefik.http.routers.{prefix}.middlewares": self.main_middlewares,
        }
        if self.longpolling_service:
            longpolling_prefix = f"{prefix}-lp"
            labels.update(
                {
                    f"traefik.http.routers.{longpolling_prefix}.rule": f"{host} && (PathPrefix(`/websocket`) || PathPrefix(`/longpolling`))",
                    f"traefik.http.routers.{longpolling_prefix}.entrypoints": "web",
                    f"traefik.http.routers.{longpolling_prefix}.service": self.longpolling_service,
                    f"traefik.http.routers.{longpolling_prefix}.priority": "200",
                }
            )
        return labels

    def static_router(self, prefix: str, domain: str, certresolver: str) -> dict[str, str]:
        host_rule = f"Host(`{domain}`) && (PathPrefix(`/web/static`) || PathPrefix(`/web/assets`))"
        if self.tls_enabled:
            return {
                f"traefik.http.routers.{prefix}.rule": host_rule,
                f"traefik.http.routers.{prefix}.entrypoints": "websecure",
                f"traefik.http.routers.{prefix}.tls": "true",
                f"traefik.http.routers.{prefix}.tls.certresolver": certresolver,
                f"traefik.http.routers.{prefix}.service": self.main_service,
                f"traefik.http.routers.{prefix}.middlewares": self.static_middlewares,
                f"traefik.http.routers.{prefix}.priority": "150",
            }
        return {
            f"traefik.http.routers.{prefix}.rule": host_rule,
            f"traefik.http.routers.{prefix}.entrypoints": "web",
            f"traefik.http.routers.{prefix}.service": self.main_service,
            f"traefik.http.routers.{prefix}.middlewares": self.static_middlewares,
            f"traefik.http.routers.{prefix}.priority": "150",
        }
