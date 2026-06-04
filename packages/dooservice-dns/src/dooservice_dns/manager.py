"""DnsManager protocol — contract every DNS manager implementation must satisfy."""

from __future__ import annotations

from typing import Protocol


class DnsManager(Protocol):
    async def ensure_record(self, fqdn: str, target: str) -> None:
        """Create or update a DNS record fqdn → target. Idempotent.

        Record type inferred from target:
          IP address  → A record
          Hostname    → CNAME record
        """
        ...

    async def remove_record(self, fqdn: str) -> None: ...

    async def close(self) -> None: ...
