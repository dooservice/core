"""Centralized constants — names, ports, paths, timeouts shared across packages."""

from __future__ import annotations

from pathlib import Path

# ── Default data dirs ────────────────────────────────────────────────────────
DEFAULT_DATA_DIR = Path("/var/lib/dooservice")
DEFAULT_PG_SUPERUSER_PASSWORD = "dooservice_super_change_me"  # noqa: S105

# ── DB ───────────────────────────────────────────────────────────────────────
MODELS_MODULE = "dooservice_db_agent.models"

# ── External APIs ────────────────────────────────────────────────────────────
CLOUDFLARE_API     = "https://api.cloudflare.com/client/v4"
HTTP_TIMEOUT_SECS  = 30

# ── Docker network ───────────────────────────────────────────────────────────
DOOSERVICE_NETWORK_NAME = "dooservice-shared-network"

# ── Postgres backend ─────────────────────────────────────────────────────────
POSTGRES_IMAGE = "ghcr.io/dooservice/dooservice-postgres:16"
POSTGRES_CONTAINER_NAME = "dooservice-postgres-backend"
POSTGRES_VOLUME_NAME = "dooservice-postgres-backend-data"
POSTGRES_DATA_DIR = "/var/lib/postgresql/data"
POSTGRES_PORT = 5432
POSTGRES_SUPERUSER = "dooservice_admin"

# ── PgDog pooler ─────────────────────────────────────────────────────────────
PGDOG_IMAGE = "ghcr.io/pgdogdev/pgdog:v0.1.34"
PGDOG_CONTAINER_NAME = "dooservice-pgdog"
PGDOG_CONFIG_DIR = "/etc/pgdog"
PGDOG_PORT = 6432
PGDOG_DEFAULT_POOL_SIZE     = 10  # per (user, tenant_db): up to 10 workers per Odoo instance
PGDOG_MAINTENANCE_POOL_SIZE = 3   # per (user, postgres): only used during db init/clone

# ── Traefik proxy ────────────────────────────────────────────────────────────
TRAEFIK_IMAGE = "traefik:latest"
TRAEFIK_CONTAINER_NAME = "dooservice-traefik"
TRAEFIK_HTTP_PORT = 80
TRAEFIK_HTTPS_PORT = 443

# ── Capture service ──────────────────────────────────────────────────────────
CAPTURE_IMAGE = "ghcr.io/bluewave-labs/capture:latest"
CAPTURE_CONTAINER_NAME = "dooservice-capture"
CAPTURE_PORT = 59232

# ── Odoo container ───────────────────────────────────────────────────────────
ODOO_IMAGE = "ghcr.io/dooservice/dooservice-odoo"
ODOO_DATA_DIR = "/var/lib/odoo"
ODOO_BACKUPS_DIR = "/mnt/backups"
ODOO_ADDONS_DIR = "/mnt/extra-addons"
ODOO_HTTP_PORT = 8069
ODOO_GEVENT_PORT = 8072

# Resource limits per Odoo container.
#
# Memory — ceil to nearest GB: ceil((BASE + workers × PER_WORKER) × SAFETY / 1024)
#   workers=1 → 2 GB, workers=2 → 3 GB, workers=4 → 4 GB, workers=8 → 7 GB
ODOO_WORKER_BASE_MB      = 1024   # master process + gevent + OS overhead
ODOO_WORKER_SIZE_MB      = 512    # memory per HTTP worker process
ODOO_MEMORY_SAFETY       = 1.25   # 25% headroom for memory spikes
#
# CPU shares — relative weight, not a hard cap (workers × SHARES_PER_WORKER).
# Default Docker value = 1024. Higher = more priority under contention.
#   workers=1 → 512, workers=2 → 1024, workers=4 → 2048, workers=8 → 4096
ODOO_CPU_SHARES_PER_WORKER = 512

# ── Docker container labels ──────────────────────────────────────────────────
LABEL_MANAGED = "dooservice.managed"
LABEL_PROJECT_ID = "dooservice.project_id"
LABEL_ENVIRONMENT_ID = "dooservice.environment_id"
LABEL_TYPE = "dooservice.type"

# ── Timeouts (seconds) ───────────────────────────────────────────────────────
ODOO_HEALTH_TIMEOUT_SECONDS = 180
CONTAINER_STOP_TIMEOUT_SECONDS = 10
SSL_READINESS_TIMEOUT_SECONDS = 120
SSL_READINESS_POLL_INTERVAL_SECONDS = 5

# ── Backup storage ───────────────────────────────────────────────────────────
MULTIPART_PART_SIZE  = 50 * 1024 * 1024  # 50 MB per upload part
DOWNLOAD_CHUNK_SIZE  = 50 * 1024 * 1024  # 50 MB per download chunk
