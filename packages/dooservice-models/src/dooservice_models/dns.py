"""DNS provider and verification models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

import msgspec


class DnsProvider(msgspec.Struct, tag_field="type"):
    """Base type for supported DNS providers (used by Traefik for DNS-01 cert challenge)."""


class CloudflareToken(DnsProvider, tag="cloudflare_token"):
    api_token: str


class CloudflareGlobalKey(DnsProvider, tag="cloudflare_global_key"):
    email: str
    api_key: str


class Route53(DnsProvider, tag="route53"):
    access_key_id: str
    secret_access_key: str
    region: str | None = None
    hosted_zone_id: str | None = None


class DigitalOcean(DnsProvider, tag="digitalocean"):
    api_token: str


class Gandi(DnsProvider, tag="gandi"):
    """Gandi v5 personal access token (GANDIV5_PERSONAL_ACCESS_TOKEN)."""

    personal_access_token: str


class OVH(DnsProvider, tag="ovh"):
    endpoint: str
    application_key: str
    application_secret: str
    consumer_key: str


class Hetzner(DnsProvider, tag="hetzner"):
    api_key: str


class Linode(DnsProvider, tag="linode"):
    token: str


class GoDaddy(DnsProvider, tag="godaddy"):
    api_key: str
    api_secret: str


class Namecheap(DnsProvider, tag="namecheap"):
    api_user: str
    api_key: str


AnyDnsProvider = (
    CloudflareToken
    | CloudflareGlobalKey
    | Route53
    | DigitalOcean
    | Gandi
    | OVH
    | Hetzner
    | Linode
    | GoDaddy
    | Namecheap
)


class DnsRecordType(StrEnum):
    A = "A"
    CNAME = "CNAME"


class DomainVerificationResult(msgspec.Struct):
    domain: str
    expected_target: str
    verified: bool
    resolved_target: str | None = None
    reason: str | None = None
    checked_at: datetime = msgspec.field(default_factory=lambda: datetime.now(UTC))
