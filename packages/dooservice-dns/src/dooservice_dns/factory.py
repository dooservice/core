"""Instantiate the right DnsManager from an AnyDnsProvider config."""

from __future__ import annotations

from dooservice_models import AnyDnsProvider, CloudflareGlobalKey, CloudflareToken

from .cloudflare import CloudflareDnsManager
from .manager import DnsManager
from .noop import NoopDnsManager


def create_dns_manager(provider: AnyDnsProvider | None) -> DnsManager:
    if provider is None:
        return NoopDnsManager()
    match provider:
        case CloudflareToken() | CloudflareGlobalKey():
            return CloudflareDnsManager(provider)
        case _:
            raise NotImplementedError(
                f"no DnsManager implemented for provider '{type(provider).__name__}'. Add a case in factory.py."
            )
