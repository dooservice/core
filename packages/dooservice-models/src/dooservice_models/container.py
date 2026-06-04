"""Container model: ContainerSpec, ContainerInfo, Healthcheck, ExecResult."""

from __future__ import annotations

from enum import StrEnum

import msgspec


class ContainerState(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    RESTARTING = "restarting"
    REMOVING = "removing"
    EXITED = "exited"
    DEAD = "dead"


class RestartPolicy(StrEnum):
    NO = "no"
    ALWAYS = "always"
    ON_FAILURE = "on-failure"
    UNLESS_STOPPED = "unless-stopped"


class HealthStatus(StrEnum):
    NONE = "none"
    STARTING = "starting"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class Healthcheck(msgspec.Struct):
    test: list[str]
    interval_seconds: int = 30
    timeout_seconds: int = 30
    retries: int = 3
    start_period_seconds: int = 0


class ContainerSpec(msgspec.Struct):
    image: str
    name: str
    env: dict[str, str] = msgspec.field(default_factory=dict)
    ports: dict[int, int] = msgspec.field(default_factory=dict)
    volumes: dict[str, str] = msgspec.field(default_factory=dict)
    labels: dict[str, str] = msgspec.field(default_factory=dict)
    network: str | None = None
    command: list[str] | None = None
    entrypoint: list[str] | None = None
    working_dir: str | None = None
    restart_policy: RestartPolicy = RestartPolicy.NO
    healthcheck: Healthcheck | None = None
    mem_limit: str | None = None        # e.g. "1920m"
    memswap_limit: str | None = None    # set equal to mem_limit to disable swap
    cpu_shares: int | None = None       # relative CPU weight (default Docker = 1024)


class ContainerInfo(msgspec.Struct):
    id: str
    name: str
    image: str
    state: ContainerState
    status: str
    health: HealthStatus = HealthStatus.NONE


class ExecResult(msgspec.Struct):
    exit_code: int
    output: str
