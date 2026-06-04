from __future__ import annotations

import msgspec


class ServiceStatus(msgspec.Struct):
    name: str
    running: bool
    container_id: str | None = None
