# dooservice core

Shared packages used by the dooservice agent and orchestrator. All packages live in a single uv workspace and are consumed by other repos via git tag.

| Repo | Description |
|---|---|
| [`dooservice/core`](https://github.com/dooservice/core) | **This repo** — shared packages |
| [`dooservice/orchestrator`](https://github.com/dooservice/orchestrator) | Central API server |
| [`dooservice/agent`](https://github.com/dooservice/agent) | Agent daemon — runs on each VPS |

---

## Table of contents

- [Packages](#packages)
  - [dooservice-sdk](#dooservice-sdk)
  - [dooservice-models](#dooservice-models)
  - [dooservice-db-agent](#dooservice-db-agent)
  - [dooservice-docker](#dooservice-docker)
  - [dooservice-dns](#dooservice-dns)
  - [dooservice-s3](#dooservice-s3)
  - [dooservice-transport](#dooservice-transport)
  - [dooservice-protocol](#dooservice-protocol)
- [Consuming this repo](#consuming-this-repo)
- [Versioning](#versioning)

---

## Packages

### `dooservice-sdk`

Unified entry point (`DooServiceSDK`) for all infrastructure operations on a VPS. Used exclusively by the agent.

```python
async with DooServiceSDK(config) as sdk:
    sdk.bootstrap     # Postgres, PgDog, Traefik lifecycle
    sdk.environments  # Odoo container provisioning and lifecycle
    sdk.backups       # Backup creation, restore, drop, S3 upload
    sdk.projects      # Project metadata
    sdk.domains       # Custom domain DNS and proxy routing
    sdk.git           # Git clone/pull for addons repos
    sdk.proxy         # Traefik proxy configuration
    sdk.docker        # Raw Docker client access
```

On `__aenter__` the SDK:
- Initialises SQLite via Tortoise ORM
- Connects to the Docker daemon
- Loads proxy config and creates the DNS manager
- Initialises Bootstrap (Postgres → PgDog → Traefik)

---

### `dooservice-models`

msgspec `Struct` domain models and `StrEnum` enumerations shared by all packages. Contains no business logic — pure data definitions.

**Key constants** (`dooservice_models.constants`):

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

**Odoo memory formula** (used when provisioning environments):

```python
limit_mb = int((1536 + workers * 512) * 1.25)
# workers=0 → ~1920 MB
# workers=4 → ~4480 MB
# workers=8 → ~7040 MB
```

---

### `dooservice-db-agent`

Tortoise ORM models and repository classes for the agent's local SQLite database (`/var/lib/dooservice/agent.db`).

Stores: projects, environments, backups, deployments, proxy config.

Repository pattern — `@staticmethod` async methods, raises typed domain errors instead of returning `None`.

---

### `dooservice-docker`

Thin async wrapper around the Python Docker SDK. Provides `DockerClient` with:

- Container and volume lifecycle (create, start, stop, remove)
- Ephemeral container execution — used for Odoo database dump/restore
- Network management (`dooservice-shared-network`)

---

### `dooservice-dns`

Async DNS manager with multi-provider support via a `DnsManager` protocol. Created via `create_dns_manager(provider)` factory from the proxy config.

**Supported providers:**

| Provider | Auth method |
|---|---|
| Cloudflare | API token or global key |
| Route53 | AWS credentials |
| DigitalOcean | Personal access token |
| Hetzner | API token |
| Linode | API token |
| GoDaddy | API key + secret |
| Namecheap | API key |
| Gandi | API key |
| OVH | Application key + secret |
| `NoopDnsManager` | No-op — for HTTP-01 TLS or manual DNS |

---

### `dooservice-s3`

Async S3 client wrapping `boto3`. Used by the agent for off-site backup storage.

Features:
- Upload and download objects
- Delete objects
- Presigned download URLs
- Multipart upload for large backup files

---

### `dooservice-transport`

NATS JetStream transport layer shared between agent and orchestrator.

**`AgentTransport`** (used by the agent):
- Subscribes to `job.inbox.<region>` and `job.inbox.agent.<agent_id>`
- Publishes `JobProgress`, `JobCompleted`, `JobFailed` to per-job subjects
- Publishes `AgentHeartbeat` (with CPU, RAM, disk metrics) every `heartbeat_interval` seconds

**`OrchestratorTransport`** (used by the orchestrator):
- Dispatches `JobSubmit` messages to agents by region via JetStream
- Sends request-reply `QueryRequest` messages to individual agents
- Subscribes to result subjects and routes progress frames to WebSocket clients

---

### `dooservice-protocol`

Wire-format msgspec structs shared between agent and orchestrator. Defines the complete message contract for Agent ↔ Orchestrator communication.

```python
# Agent → Orchestrator (results stream)
JobProgress(job_id, stage, pct)
JobCompleted(job_id, result)
JobFailed(job_id, error)
AgentHeartbeat(agent_id, region, cpu_percent, mem_used_gb, mem_total_gb, disk_used_gb, disk_total_gb)

# Orchestrator → Agent (JetStream dispatch)
JobSubmit(job_id, kind, args)

# Orchestrator → Agent (request-reply)
QueryRequest(kind, args)
QueryResponse(ok, data, error)
```

---

## Consuming this repo

Packages are referenced via git tag in `pyproject.toml`:

```toml
[tool.uv.sources]
dooservice-sdk = {
    git = "https://github.com/dooservice/core",
    subdirectory = "packages/dooservice-sdk",
    tag = "core/v1.10.0"
}
```

All 8 packages share the same tag. When updating, change the tag in all `[tool.uv.sources]` entries and run `uv sync`.

For local development, replace the git reference with a path:

```toml
dooservice-sdk = { path = "../core/packages/dooservice-sdk", editable = true }
```

---

## Versioning

All packages are versioned together under a single `core/vX.Y.Z` tag. A tag on this repo is the authoritative version reference for both `dooservice/agent` and `dooservice/orchestrator`.
