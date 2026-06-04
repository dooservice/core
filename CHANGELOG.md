# Changelog

All notable changes to the dooservice core packages are documented here.
All packages are versioned together under a single `core/vX.Y.Z` tag.

## [1.8.1] — 2026-06-01

### `dooservice-sdk`
- `EnvironmentService._health_check_passes()`: replaces the raw TLS handshake with an `httpx` GET to `/web/health` — validates SSL cert, Traefik route, and Odoo readiness in one call; fixes the 404 shown on first load when re-creating an instance whose cert was already cached by Traefik

---

## [1.8.0] — 2026-06-01

### `dooservice-models`
- New constants `SSL_READINESS_TIMEOUT_SECONDS = 120` and `SSL_READINESS_POLL_INTERVAL_SECONDS = 5` — control the SSL certificate polling window after container start

### `dooservice-sdk`
- `EnvironmentService.wait_for_ssl()`: polls the environment's primary domain on port 443 via TLS handshake until the Let's Encrypt certificate is ready (or the timeout is reached), then logs a warning and continues without failing the job
- `EnvProvision` and `EnvClone` job handlers: new `"Waiting for SSL certificate"` progress step (82 %) inserted after container start — the URL is guaranteed to be reachable over HTTPS when the job completes

---

## [1.7.0] — 2026-05-26

### `dooservice-models`
- `ProxyConfig`: new `secondary_domains: list[str]` field — proxy can serve environments under multiple root domains
- `ProxyConfig.primary_domain_for()`: accepts optional `base_domain` parameter to assign an environment under a specific root domain instead of the default
- `ProxyConfig.all_base_domains()`: new helper returning `[base_domain] + secondary_domains`
- `ProxyStatus`: new `secondary_domains: list[str]` field
- `ProxyTlsConfig`, `ProxyConfig`, `ProxyStatus`: all fields now use consistent `msgspec.field()` declarations

### `dooservice-sdk`
- `ProxyDefaults` (`config.py`): `secondary_domains: list[str]` field — reads from TOML or `DOOSERVICE_SECONDARY_DOMAINS` env var (JSON array)
- `Bootstrap.configure()`: accepts `secondary_domains: list[str] | None` and persists it to `ProxyConfig`
- `TraefikProxyService.status()`: includes `secondary_domains` in the returned `ProxyStatus`
- `EnvironmentService.configure_dns()`: optional `base_domain: str` parameter — pass one of the secondary domains to assign the environment under that root
- `EnvProvision` and `EnvClone` job handlers: propagate `base_domain` from job args to `configure_dns()`

### `dooservice-protocol`
- `EnvProvisionArgs`: new `base_domain: str = ""` field — orchestrator sets this when provisioning under a secondary domain
- `EnvCloneArgs`: new `base_domain: str = ""` field

### `dooservice-transport`
- `AgentHeartbeat`: new `secondary_domains: list[str]` field — agent reports its configured secondary domains on every heartbeat
- `AgentTransport`: new `secondary_domains` constructor parameter, included in every heartbeat publish

---

## [1.6.0] — 2026-05-24

### `dooservice-transport`
- `AgentHeartbeat`: new optional fields `mem_used_gb: float | None`, `mem_total_gb: float | None` — agent reports raw memory usage alongside the existing percentage
- `AgentTransport.send_heartbeat()`: accepts `mem_used_gb` and `mem_total_gb` parameters

---

## [1.5.0] — 2026-05-24

### `dooservice-transport`
- `AgentHeartbeat`: new optional fields `cpu_percent: float | None`, `mem_percent: float | None`, `disk_used_gb: float | None`, `disk_total_gb: float | None` — agent reports server resource usage on every heartbeat
- `AgentTransport.send_heartbeat()`: accepts the 4 new resource metric parameters and includes them in the published message

---

## [1.4.0] — 2026-05-23

### `dooservice-transport`
- `AgentHeartbeat`: new `uptime_seconds: int = 0`, `last_backup_at: str | None = None`, `last_backup_ok: bool | None = None` fields — agent reports process uptime and last backup status on every heartbeat
- `AgentTransport.send_heartbeat()`: accepts `uptime_seconds`, `last_backup_at`, `last_backup_ok` parameters and includes them in the published message

### `dooservice-db-agent`
- `BackupRepository.get_latest()`: new method — returns the most recent backup record across all environments regardless of status

---

## [1.3.0] — 2026-05-22

### `dooservice-transport`
- `AgentHeartbeat`: new `base_domain: str = ""` field — orchestrator learns each agent's base domain via heartbeat
- `AgentTransport`: new `base_domain` constructor parameter, included in every heartbeat publish

---

## [1.2.2] — 2026-05-22

### Fixed
- `CaptureService`: added `GIN_MODE=release` env var — container was starting in debug mode

---

## [1.2.1] — 2026-05-22

### Fixed
- `CaptureService`: removed `:ro` suffix from `/etc/os-release` volume path — docker-py requires a plain path in the bind field; the suffix caused container creation to fail silently

---

## [1.2.0] — 2026-05-22

### `dooservice-models`
- Added `CAPTURE_IMAGE`, `CAPTURE_CONTAINER_NAME`, `CAPTURE_PORT` constants for the Bluewave Capture screenshot service

### `dooservice-sdk`
- `Config`: new `capture_api_secret` and `capture_hostname` fields, loaded from `DOOSERVICE_CAPTURE_API_SECRET` and `DOOSERVICE_CAPTURE_HOSTNAME` env vars
- `CaptureService`: new bootstrap service managing the Capture container lifecycle — `ensure_running()`, `stop()`, `destroy()`, `status()`; domain is `{hostname}.{base_domain}` where hostname defaults to `socket.gethostname()`
- `Bootstrap`: receives `DnsManager`; wires in `CaptureService`; `ensure_running()` starts the Capture container and creates its DNS A record in Cloudflare automatically; `status()` now returns a 4-tuple including capture status

---

## [1.1.0] — 2026-05-22

### `dooservice-models`
- Renamed memory constants: `ODOO_MEMORY_BASE_MB` → `ODOO_WORKER_BASE_MB`, `ODOO_MEMORY_PER_WORKER_MB` → `ODOO_WORKER_SIZE_MB`, `ODOO_MEMORY_OVERHEAD_FACTOR` → `ODOO_MEMORY_SAFETY`
- Added `ODOO_CPU_SHARES_PER_WORKER = 512` — relative Docker CPU weight per Odoo worker
- `ContainerSpec`: new fields `memswap_limit` and `cpu_shares`

### `dooservice-docker`
- `container_spec_to_kwargs`: passes `memswap_limit` and `cpu_shares` to Docker SDK when set

### `dooservice-sdk`
- Replaced `memory_limit_for_workers()` with `OdooResourceLimits` class: `memory()`, `memswap()`, `cpu_shares()` static methods
- Memory formula now rounds up to the nearest GB instead of returning raw MB
- Swap disabled by default (`memswap_limit = mem_limit`) to prevent latency spikes
- CPU shares wired into `build_spec()` via `ContainerSpec.cpu_shares`

---

## [1.0.0] — 2026-05-22

### `dooservice-sdk`
- `DooServiceSDK`: unified async context manager initialising Docker, SQLite, PgDog, Postgres, DNS manager, and Bootstrap
- `BackupService.drop()`: deletes physical file (S3 or local) and marks record `DROPPED` — record never deleted
- `Bootstrap.configure()`: owns the full proxy setup use case — resolves defaults, builds DNS provider, persists to DB
- `Bootstrap.build_dns_provider()`: builds `AnyDnsProvider` from kind string + credentials

### `dooservice-models`
- Domain structs (`msgspec.Struct`) and `StrEnum` enums for all domain concepts
- `DEFAULT_DATA_DIR = /var/lib/dooservice`
- Docker image constants using `ghcr.io/dooservice/` registry
- Odoo memory formula constants: base 1536 MB + 512 MB/worker × 1.25 safety factor

### `dooservice-db-agent`
- Tortoise ORM models for agent SQLite: projects, environments, backups, deployments, proxy config
- `BackupRepository.list_completed_scheduled()`: returns all completed scheduled backups for an environment
- `BackupRepository.mark_dropped()`: marks record DROPPED without deleting it

### `dooservice-docker`
- Async Docker SDK wrapper with ephemeral container execution for Odoo dump/restore operations

### `dooservice-dns`
- Multi-provider async DNS manager: Cloudflare (token/global key), Route53, DigitalOcean, Hetzner, Linode, GoDaddy, Namecheap, Gandi, OVH, Noop

### `dooservice-s3`
- Async S3 client: upload, download, delete, presigned URLs, multipart upload

### `dooservice-transport`
- `AgentTransport`: NATS JetStream subscription for job inbox, publishes results and heartbeats
- `OrchestratorTransport`: dispatches jobs by region, streams results

### `dooservice-protocol`
- Wire-format structs: `JobSubmit`, `JobProgress`, `JobCompleted`, `JobFailed`, `AgentHeartbeat`, `QueryRequest`, `QueryResponse`
