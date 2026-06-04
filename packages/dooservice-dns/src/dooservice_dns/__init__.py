"""DNS management and CNAME verification."""

from .cloudflare import CloudflareDnsManager
from .errors import (
    DnsApiError,
    DnsError,
    DnsNetworkError,
    DnsResolutionError,
    ZoneNotFoundError,
)
from .factory import create_dns_manager
from .manager import DnsManager
from .noop import NoopDnsManager
from .resolver import verify_cname_record

__all__ = [
    "CloudflareDnsManager",
    "DnsApiError",
    "DnsError",
    "DnsManager",
    "DnsNetworkError",
    "DnsResolutionError",
    "NoopDnsManager",
    "ZoneNotFoundError",
    "create_dns_manager",
    "verify_cname_record",
]
