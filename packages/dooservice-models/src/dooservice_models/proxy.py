"""Proxy and TLS configuration models."""

from __future__ import annotations

from datetime import UTC, datetime

import msgspec

from .constants import (
    DOOSERVICE_NETWORK_NAME,
    TRAEFIK_CONTAINER_NAME,
    TRAEFIK_HTTP_PORT,
    TRAEFIK_HTTPS_PORT,
)
from .dns import AnyDnsProvider


class ProxyTlsConfig(msgspec.Struct):
    enabled:      bool                  = msgspec.field(default=False)
    acme_email:   str                   = msgspec.field(default="")
    use_wildcard: bool                  = msgspec.field(default=False)
    dns_provider: AnyDnsProvider | None = msgspec.field(default=None)
    staging:      bool                  = msgspec.field(default=False)


class ProxyConfig(msgspec.Struct):
    network_name:      str            = msgspec.field(default=DOOSERVICE_NETWORK_NAME)
    container_name:    str            = msgspec.field(default=TRAEFIK_CONTAINER_NAME)
    base_domain:       str            = msgspec.field(default="")
    secondary_domains: list[str]      = msgspec.field(default_factory=list)
    http_port:         int            = msgspec.field(default=TRAEFIK_HTTP_PORT)
    https_port:        int            = msgspec.field(default=TRAEFIK_HTTPS_PORT)
    dashboard_enabled: bool           = msgspec.field(default=False)
    dashboard_domain:  str            = msgspec.field(default="")
    container_id:      str | None     = msgspec.field(default=None)
    server_ip:         str | None     = msgspec.field(default=None)
    tls:               ProxyTlsConfig = msgspec.field(default_factory=ProxyTlsConfig)
    created_at:        datetime       = msgspec.field(default_factory=lambda: datetime.now(UTC))
    updated_at:        datetime       = msgspec.field(default_factory=lambda: datetime.now(UTC))

    def primary_domain_for(self, environment_name: str, base_domain: str = "") -> str:
        root = base_domain or self.base_domain
        return f"{environment_name}.{root}" if root else ""

    def all_base_domains(self) -> list[str]:
        domains = [self.base_domain] if self.base_domain else []
        return domains + self.secondary_domains

    def dashboard_host(self) -> str:
        if self.dashboard_domain:
            return self.dashboard_domain
        return f"traefik.{self.base_domain}" if self.base_domain else ""


class ProxyStatus(msgspec.Struct):
    running:           bool       = msgspec.field(default=False)
    base_domain:       str        = msgspec.field(default="")
    secondary_domains: list[str]  = msgspec.field(default_factory=list)
    container_id:      str | None = msgspec.field(default=None)
    dashboard_domain:  str        = msgspec.field(default="")
