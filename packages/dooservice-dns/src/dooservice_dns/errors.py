"""DNS errors."""

from __future__ import annotations


class DnsError(Exception):
    pass


class DnsApiError(DnsError):
    def __init__(self, endpoint: str, reason: str) -> None:
        super().__init__(f"DNS API error calling {endpoint}: {reason}")


class DnsNetworkError(DnsError):
    def __init__(self, endpoint: str, reason: str) -> None:
        super().__init__(f"DNS network failure calling {endpoint}: {reason}")


class ZoneNotFoundError(DnsError):
    def __init__(self, domain: str) -> None:
        super().__init__(f"DNS zone not found for domain: {domain}")


class DnsResolutionError(DnsError):
    def __init__(self, domain: str, reason: str) -> None:
        super().__init__(f"DNS resolution failed for {domain}: {reason}")
