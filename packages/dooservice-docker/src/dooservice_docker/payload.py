"""Translate domain specs to docker-py payloads, and back."""

from __future__ import annotations

from dooservice_models import (
    ContainerSpec,
    Healthcheck,
)

NANOSECONDS_PER_SECOND = 1_000_000_000


def healthcheck_to_payload(healthcheck: Healthcheck) -> dict:
    return {
        "test": healthcheck.test,
        "interval": healthcheck.interval_seconds * NANOSECONDS_PER_SECOND,
        "timeout": healthcheck.timeout_seconds * NANOSECONDS_PER_SECOND,
        "retries": healthcheck.retries,
        "start_period": healthcheck.start_period_seconds * NANOSECONDS_PER_SECOND,
    }


def ports_to_payload(ports: dict[int, int]) -> dict[str, int]:
    return {f"{container_port}/tcp": host_port for container_port, host_port in ports.items()}


def volumes_to_payload(volumes: dict[str, str]) -> dict[str, dict[str, str]]:
    return {host_path: {"bind": container_path, "mode": "rw"} for host_path, container_path in volumes.items()}


def container_spec_to_kwargs(spec: ContainerSpec) -> dict:
    kwargs: dict = {
        "image": spec.image,
        "name": spec.name,
        "environment": spec.env,
        "ports": ports_to_payload(spec.ports),
        "volumes": volumes_to_payload(spec.volumes),
        "labels": spec.labels,
        "restart_policy": {"Name": spec.restart_policy.value},
        "detach": True,
    }
    if spec.network:
        kwargs["network"] = spec.network
    if spec.command:
        kwargs["command"] = spec.command
    if spec.entrypoint:
        kwargs["entrypoint"] = spec.entrypoint
    if spec.working_dir:
        kwargs["working_dir"] = spec.working_dir
    if spec.healthcheck:
        kwargs["healthcheck"] = healthcheck_to_payload(spec.healthcheck)
    if spec.mem_limit:
        kwargs["mem_limit"] = spec.mem_limit
    if spec.memswap_limit:
        kwargs["memswap_limit"] = spec.memswap_limit
    if spec.cpu_shares:
        kwargs["cpu_shares"] = spec.cpu_shares
    return kwargs
