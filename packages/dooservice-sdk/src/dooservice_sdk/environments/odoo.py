"""Odoo container spec builder."""

from __future__ import annotations

import math
from pathlib import Path

from dooservice_models import (
    DOOSERVICE_NETWORK_NAME,
    LABEL_ENVIRONMENT_ID,
    LABEL_MANAGED,
    LABEL_PROJECT_ID,
    LABEL_TYPE,
    ODOO_ADDONS_DIR,
    ODOO_CPU_SHARES_PER_WORKER,
    ODOO_DATA_DIR,
    ODOO_IMAGE,
    ODOO_MEMORY_SAFETY,
    ODOO_WORKER_BASE_MB,
    ODOO_WORKER_SIZE_MB,
    POSTGRES_CONTAINER_NAME,
    POSTGRES_PORT,
    ContainerSpec,
    Environment,
    Healthcheck,
    RestartPolicy,
)

from ..proxy.labels import OdooRoutingLabels

ODOO_CONFIG_DIR  = "/etc/odoo"
ODOO_CONFIG_FILE = f"{ODOO_CONFIG_DIR}/odoo.conf"


class OdooResourceLimits:
    """Docker resource limits for an Odoo container based on worker count.

    Valid worker values: 1, 2, 4, 8.

    Memory: hard cap — container is killed if it exceeds the limit.
    Swap:   disabled (memswap = mem_limit) — prevents latency spikes from swap.
    CPU:    soft weight via cpu_shares — no hard cap, ensures fair scheduling
            across all instances on the VPS without blocking idle CPU capacity.
    """

    @staticmethod
    def memory(workers: int) -> str:
        raw_mb = (ODOO_WORKER_BASE_MB + workers * ODOO_WORKER_SIZE_MB) * ODOO_MEMORY_SAFETY
        gb = math.ceil(raw_mb / 1024)
        return f"{gb}g"

    @staticmethod
    def memswap(workers: int) -> str:
        return OdooResourceLimits.memory(workers)

    @staticmethod
    def cpu_shares(workers: int) -> int:
        return workers * ODOO_CPU_SHARES_PER_WORKER


def build_spec(
    environment: Environment,
    *,
    tls_enabled: bool = False,
    addons_dir: Path | None = None,
    config_dir: Path | None = None,
) -> ContainerSpec:
    labels = {
        LABEL_MANAGED: "true",
        LABEL_PROJECT_ID: str(environment.project_id),
        LABEL_ENVIRONMENT_ID: str(environment.id),
        LABEL_TYPE: "odoo",
    }
    proxy_network = environment.config.proxy_network_name or DOOSERVICE_NETWORK_NAME
    labels.update(OdooRoutingLabels(environment, proxy_network, tls_enabled=tls_enabled).build())

    volumes: dict[str, str] = {f"odoo_data_{environment.id.hex}": ODOO_DATA_DIR}
    if addons_dir is not None:
        volumes[str(addons_dir)] = ODOO_ADDONS_DIR
    if config_dir is not None:
        volumes[str(config_dir)] = ODOO_CONFIG_DIR

    total_workers = environment.config.base_workers + environment.config.extra_workers
    limits = OdooResourceLimits
    return ContainerSpec(
        image=f"{ODOO_IMAGE}:{environment.odoo_version}",
        name=f"odoo_{environment.id.hex}",
        env={"TZ": environment.config.timezone},
        command=build_cmd(),
        labels=labels,
        volumes=volumes,
        network=DOOSERVICE_NETWORK_NAME,
        healthcheck=Healthcheck(
            test=["CMD", "curl", "-f", "http://localhost:8069/web/health"],
            interval_seconds=10,
            timeout_seconds=5,
            retries=5,
            start_period_seconds=30,
        ),
        restart_policy=RestartPolicy.UNLESS_STOPPED,
        mem_limit=limits.memory(total_workers),
        memswap_limit=limits.memswap(total_workers),
        cpu_shares=limits.cpu_shares(total_workers),
    )


def build_cmd() -> list[str]:
    return ["odoo", "-c", ODOO_CONFIG_FILE]


def build_dump_cmd(environment: Environment, container_path: str, *, with_filestore: bool = True) -> list[str]:
    config = environment.config
    cmd = [
        "odoo", "db",
        f"--db_host={POSTGRES_CONTAINER_NAME}",
        f"--db_port={POSTGRES_PORT}",
        f"--db_user={config.pg_db_user}",
        f"--db_password={config.pg_db_password}",
        f"--data-dir={ODOO_DATA_DIR}",
        "dump", config.pg_db_name, container_path,
        "--format", "zip",
    ]
    if not with_filestore:
        cmd.append("--no-filestore")
    return cmd


def build_load_cmd(environment: Environment, container_path: str, *, neutralize: bool = False) -> list[str]:
    config = environment.config
    cmd = [
        "odoo", "db",
        f"--db_host={POSTGRES_CONTAINER_NAME}",
        f"--db_port={POSTGRES_PORT}",
        f"--db_user={config.pg_db_user}",
        f"--db_password={config.pg_db_password}",
        f"--data-dir={ODOO_DATA_DIR}",
        "load", "--force",
    ]
    if neutralize:
        cmd.append("--neutralize")
    cmd += [config.pg_db_name, container_path]
    return cmd


def build_db_neutralize_cmd(environment: Environment) -> list[str]:
    return [
        "odoo", "neutralize",
        "-c", ODOO_CONFIG_FILE,
        "-d", environment.config.pg_db_name,
    ]


def build_db_init_command(environment: Environment) -> list[str]:
    config = environment.config
    return [
        "odoo", "db",
        f"--db_host={POSTGRES_CONTAINER_NAME}",
        f"--db_port={POSTGRES_PORT}",
        f"--db_user={config.pg_db_user}",
        f"--db_password={config.pg_db_password}",
        "init", config.pg_db_name,
        f"--username={config.admin_email or 'admin'}",
        f"--password={config.admin_password or 'admin'}",
        f"--language={config.language}",
    ]
