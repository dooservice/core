# dooservice core

Shared packages used by the dooservice agent and orchestrator. All packages live in a single uv workspace and are referenced by consumers via git tag.

| Repo | Description |
|---|---|
| [`dooservice/agent`](https://github.com/dooservice/agent) | Agent daemon |
| [`dooservice/orchestrator`](https://github.com/dooservice/orchestrator) | Orchestrator server |
| [`dooservice/core`](https://github.com/dooservice/core) | **This repo** |

---

## Packages

### `dooservice-sdk`

Unified entry point (`DooServiceSDK`) for all infrastructure operations. Used exclusively by the agent.

```python
async with DooServiceSDK(config) as sdk:
    sdk.bootstrap    # Bootstrap — Postgres, PgDog, Traefik lifecycle
    sdk.environments # Odoo container provisioning and lifecycle
    sdk.backups      # Backup creation, restore, drop, S3 upload
    sdk.projects     # Project metadata
    sdk.domains      # Custom domain DNS and proxy routing
    sdk.git          # Git clone/pull for addons repos
    sdk.proxy        # Traefik proxy configuration
    sdk.docker       # Raw Docker client access
```

On `__aenter__`:
- Initialises SQLite via Tortoise ORM
- Connects to Docker daemon
- Loads proxy config and creates DNS manager
- Initialises Bootstrap (Postgres + PgDog + Traefik services)

### `dooservice-models`

msgspec `Struct` domain models and `StrEnum` enumerations shared by all packages. No business logic.

Key constants (`dooservice_models.constants`):

| Constant | Value |
|---|---|
| `DEFAULT_DATA_DIR` | `/var/lib/dooservice` |
| `DOOSERVICE_NETWORK_NAME` | `dooservice-shared-network` |
| `ODOO_IMAGE` | `ghcr.io/dooservice/dooservice-odoo` |
| `POSTGRES_IMAGE` | `ghcr.io/dooservice/dooservice-postgres:16` |
| `PGDOG_IMAGE` | `ghcr.io/pgdogdev/pgdog:v0.1.34` |
| `ODOO_HTTP_PORT` | `8069` |
| `ODOO_GEVENT_PORT` | `8072` |
| `PGDOG_PORT` | `6432` |
| `POSTGRES_PORT` | `5432` |

Odoo memory formula:
```
limit_mb = int((1536 + workers * 512) * 1.25)
# workers=0 → ~1920 MB   workers=4 → ~4480 MB   workers=8 → ~7040 MB
```

### `dooservice-db-agent`

Tortoise ORM models and repository classes for the agent's local SQLite database (`/var/lib/dooservice/agent.db`). Stores: projects, environments, backups, deployments, proxy config.

Repository pattern — `@staticmethod` async methods, raises domain errors instead of returning `None`.

### `dooservice-docker`

Thin async wrapper around the Python Docker SDK. Provides `DockerClient` with methods for container and volume lifecycle, ephemeral container execution (used for Odoo dump/restore), and network management.

### `dooservice-dns`

Async DNS manager supporting multiple providers via a `DnsManager` protocol:
- Cloudflare (token or global key)
- Route53, DigitalOcean, Hetzner, Linode, GoDaddy, Namecheap, Gandi, OVH
- `NoopDnsManager` for HTTP-01 TLS or manual DNS

Created via `create_dns_manager(provider)` factory from the proxy config.

### `dooservice-s3`

Async S3 client wrapping `boto3`. Supports upload, download, delete, presigned URLs, and multipart uploads. Used for off-site backup storage.

### `dooservice-transport`

NATS JetStream transport layer. Two implementations:

**`AgentTransport`** (used by the agent):
- Subscribes to `job.inbox.<region>` and `job.inbox.agent.<agent_id>`
- Publishes `JobProgress`, `JobCompleted`, `JobFailed` to per-job subjects
- Publishes `AgentHeartbeat` every `heartbeat_interval` seconds

**`OrchestratorTransport`** (used by the orchestrator):
- Dispatches jobs to agents by region
- Subscribes to all result subjects and routes to WebSocket clients

### `dooservice-protocol`

Wire-format msgspec structs shared between agent and orchestrator:

```python
# Agent → Orchestrator
JobProgress(job_id, stage, pct)
JobCompleted(job_id, result)
JobFailed(job_id, error)
AgentHeartbeat(agent_id, region)

# Orchestrator → Agent (JetStream)
JobSubmit(job_id, kind, args)

# Orchestrator → Agent (request-reply)
QueryRequest(kind, args)
QueryResponse(ok, data, error)
```

---

## Development

```bash
git clone git@github.com:dooservice/core.git
cd core
uv sync       # installs all 8 packages in editable mode
make check    # ruff lint + format
make test     # pytest across all packages
```

---

## Release

All packages in this repo are versioned together under a single `core/vX.Y.Z` tag.

```bash
# 1. Make your changes across one or more packages
# 2. Update CHANGELOG.md
# 3. Run:
make bump VERSION=1.1.0
```

This will:
- Commit any staged changes with `chore: bump core to 1.1.0`
- Tag `core/v1.1.0`
- Push branch and tag to `origin/main`

After a core release, update both `dooservice/agent` and `dooservice/orchestrator` to use the new tag in their `[tool.uv.sources]`.

---

## Consuming in Agent / Orchestrator

```toml
# pyproject.toml [tool.uv.sources]
dooservice-sdk = {
    git = "https://github.com/dooservice/core",
    subdirectory = "packages/dooservice-sdk",
    tag = "core/v1.0.0"
}
```

To use a local checkout during development, replace the git reference with a path:

```toml
dooservice-sdk = { path = "../core/packages/dooservice-sdk", editable = true }
```
