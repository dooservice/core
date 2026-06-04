"""Cloudflare DNS manager — manages A and CNAME records via the Cloudflare API.

Supports both auth methods:
  - CloudflareToken     → API Token (recommended, scoped to Zone:DNS:Edit)
  - CloudflareGlobalKey → Global API Key (full-account, fallback)

`ensure_record` auto-detects the record type from the target:
  - IP address (e.g. "1.2.3.4")        → A record
  - Hostname (e.g. "srv.example.com")  → CNAME record
"""

from __future__ import annotations

import ipaddress
from typing import Any

import httpx

from dooservice_models import CLOUDFLARE_API, HTTP_TIMEOUT_SECS, CloudflareGlobalKey, CloudflareToken

from .errors import DnsApiError, DnsNetworkError, ZoneNotFoundError


class CloudflareDnsManager:
    def __init__(self, provider: CloudflareToken | CloudflareGlobalKey) -> None:
        match provider:
            case CloudflareToken(api_token=token):
                auth_headers = {"Authorization": f"Bearer {token}"}
            case CloudflareGlobalKey(email=email, api_key=key):
                auth_headers = {"X-Auth-Email": email, "X-Auth-Key": key}
        self.client = httpx.AsyncClient(
            base_url=CLOUDFLARE_API,
            headers={**auth_headers, "Content-Type": "application/json"},
            timeout=HTTP_TIMEOUT_SECS,
        )

    async def __aenter__(self) -> CloudflareDnsManager:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self.client.aclose()

    @staticmethod
    def record_type(target: str) -> str:
        try:
            ipaddress.ip_address(target)
            return "A"
        except ValueError:
            return "CNAME"

    async def ensure_record(self, fqdn: str, target: str) -> None:
        record_type = self.record_type(target)
        zone_id = await self.get_zone_id(fqdn)
        payload = {"type": record_type, "name": fqdn, "content": target, "ttl": 1, "proxied": False}
        existing = await self.find_record(zone_id, fqdn, record_type)
        if existing and existing["content"].rstrip(".") == target.rstrip("."):
            return
        if existing:
            await self.request("PUT", f"/zones/{zone_id}/dns_records/{existing['id']}", json=payload)
        else:
            await self.request("POST", f"/zones/{zone_id}/dns_records", json=payload)

    async def remove_record(self, fqdn: str) -> None:
        zone_id = await self.get_zone_id(fqdn)
        for record_type in ("A", "CNAME"):
            existing = await self.find_record(zone_id, fqdn, record_type)
            if existing:
                await self.request("DELETE", f"/zones/{zone_id}/dns_records/{existing['id']}")
                return

    async def get_zone_id(self, fqdn: str) -> str:
        parts = fqdn.split(".")
        for index in range(len(parts) - 1):
            candidate = ".".join(parts[index:])
            data = await self.request("GET", "/zones", params={"name": candidate})
            zones = data.get("result", [])
            if zones:
                return zones[0]["id"]
        raise ZoneNotFoundError(fqdn)

    async def find_record(self, zone_id: str, fqdn: str, record_type: str) -> dict[str, Any] | None:
        data = await self.request("GET", f"/zones/{zone_id}/dns_records", params={"type": record_type, "name": fqdn})
        records = data.get("result", [])
        return records[0] if records else None

    async def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = await self.client.request(method, path, **kwargs)
        except httpx.HTTPError as error:
            raise DnsNetworkError(path, str(error)) from error
        if response.status_code >= 400:
            raise DnsApiError(path, f"HTTP {response.status_code}: {response.text}")
        data = response.json()
        if not data.get("success", False):
            errors = data.get("errors", [])
            reason = "; ".join(f"[{e.get('code', 0)}] {e.get('message', '')}" for e in errors) or "unknown"
            raise DnsApiError(path, reason)
        return data
