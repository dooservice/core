"""No-op DNS manager — for local or manually-managed deployments."""

from __future__ import annotations


class NoopDnsManager:
    async def ensure_record(self, fqdn: str, target: str) -> None:
        pass

    async def remove_record(self, fqdn: str) -> None:
        pass

    async def close(self) -> None:
        pass
