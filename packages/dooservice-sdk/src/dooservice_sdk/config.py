"""DooService runtime configuration — loaded from a TOML file or environment variables."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path

from dotenv import load_dotenv
import tomlkit

from dooservice_models import DEFAULT_DATA_DIR, DEFAULT_PG_SUPERUSER_PASSWORD


@dataclass(slots=True)
class S3Config:
    endpoint: str = ""
    access_key: str = ""
    secret_key: str = ""
    bucket: str = "dooservice-backups"
    region: str = "us-east-1"

    @property
    def enabled(self) -> bool:
        return bool(self.endpoint and self.access_key and self.secret_key)

    @classmethod
    def from_env(cls) -> S3Config:
        return cls(
            endpoint=os.environ.get("DOOSERVICE_S3_ENDPOINT", ""),
            access_key=os.environ.get("DOOSERVICE_S3_ACCESS_KEY", ""),
            secret_key=os.environ.get("DOOSERVICE_S3_SECRET_KEY", ""),
            bucket=os.environ.get("DOOSERVICE_S3_BUCKET", "dooservice-backups"),
            region=os.environ.get("DOOSERVICE_S3_REGION", "us-east-1"),
        )

    @classmethod
    def from_dict(cls, data: dict) -> S3Config:
        return cls(
            endpoint=data.get("endpoint", ""),
            access_key=data.get("access_key", ""),
            secret_key=data.get("secret_key", ""),
            bucket=data.get("bucket", "dooservice-backups"),
            region=data.get("region", "us-east-1"),
        )


@dataclass(slots=True)
class DnsProviderCredentials:
    cloudflare_api_token: str = ""
    cloudflare_email: str = ""
    cloudflare_global_key: str = ""

    route53_access_key_id: str = ""
    route53_secret_access_key: str = ""
    route53_region: str = ""
    route53_hosted_zone_id: str = ""

    digitalocean_api_token: str = ""
    gandi_personal_access_token: str = ""

    ovh_endpoint: str = ""
    ovh_application_key: str = ""
    ovh_application_secret: str = ""
    ovh_consumer_key: str = ""

    hetzner_api_key: str = ""
    linode_token: str = ""
    godaddy_api_key: str = ""
    godaddy_api_secret: str = ""
    namecheap_api_user: str = ""
    namecheap_api_key: str = ""

    @classmethod
    def from_env(cls) -> DnsProviderCredentials:
        return cls(
            cloudflare_api_token=os.environ.get("DOOSERVICE_CLOUDFLARE_API_TOKEN", ""),
            cloudflare_email=os.environ.get("DOOSERVICE_CLOUDFLARE_EMAIL", ""),
            cloudflare_global_key=os.environ.get("DOOSERVICE_CLOUDFLARE_GLOBAL_KEY", ""),
            route53_access_key_id=os.environ.get("DOOSERVICE_ROUTE53_ACCESS_KEY_ID", ""),
            route53_secret_access_key=os.environ.get("DOOSERVICE_ROUTE53_SECRET_ACCESS_KEY", ""),
            route53_region=os.environ.get("DOOSERVICE_ROUTE53_REGION", ""),
            route53_hosted_zone_id=os.environ.get("DOOSERVICE_ROUTE53_HOSTED_ZONE_ID", ""),
            digitalocean_api_token=os.environ.get("DOOSERVICE_DIGITALOCEAN_API_TOKEN", ""),
            gandi_personal_access_token=os.environ.get("DOOSERVICE_GANDI_PERSONAL_ACCESS_TOKEN", ""),
            ovh_endpoint=os.environ.get("DOOSERVICE_OVH_ENDPOINT", ""),
            ovh_application_key=os.environ.get("DOOSERVICE_OVH_APPLICATION_KEY", ""),
            ovh_application_secret=os.environ.get("DOOSERVICE_OVH_APPLICATION_SECRET", ""),
            ovh_consumer_key=os.environ.get("DOOSERVICE_OVH_CONSUMER_KEY", ""),
            hetzner_api_key=os.environ.get("DOOSERVICE_HETZNER_API_KEY", ""),
            linode_token=os.environ.get("DOOSERVICE_LINODE_TOKEN", ""),
            godaddy_api_key=os.environ.get("DOOSERVICE_GODADDY_API_KEY", ""),
            godaddy_api_secret=os.environ.get("DOOSERVICE_GODADDY_API_SECRET", ""),
            namecheap_api_user=os.environ.get("DOOSERVICE_NAMECHEAP_API_USER", ""),
            namecheap_api_key=os.environ.get("DOOSERVICE_NAMECHEAP_API_KEY", ""),
        )

    @classmethod
    def from_dict(cls, data: dict) -> DnsProviderCredentials:
        return cls(
            cloudflare_api_token=data.get("cloudflare_api_token", ""),
            cloudflare_email=data.get("cloudflare_email", ""),
            cloudflare_global_key=data.get("cloudflare_global_key", ""),
            route53_access_key_id=data.get("route53_access_key_id", ""),
            route53_secret_access_key=data.get("route53_secret_access_key", ""),
            route53_region=data.get("route53_region", ""),
            route53_hosted_zone_id=data.get("route53_hosted_zone_id", ""),
            digitalocean_api_token=data.get("digitalocean_api_token", ""),
            gandi_personal_access_token=data.get("gandi_personal_access_token", ""),
            ovh_endpoint=data.get("ovh_endpoint", ""),
            ovh_application_key=data.get("ovh_application_key", ""),
            ovh_application_secret=data.get("ovh_application_secret", ""),
            ovh_consumer_key=data.get("ovh_consumer_key", ""),
            hetzner_api_key=data.get("hetzner_api_key", ""),
            linode_token=data.get("linode_token", ""),
            godaddy_api_key=data.get("godaddy_api_key", ""),
            godaddy_api_secret=data.get("godaddy_api_secret", ""),
            namecheap_api_user=data.get("namecheap_api_user", ""),
            namecheap_api_key=data.get("namecheap_api_key", ""),
        )


@dataclass(slots=True)
class ProxyDefaults:
    base_domain:       str       = field(default="")
    secondary_domains: list[str] = field(default_factory=list)
    acme_email:        str       = field(default="")
    acme_staging:      bool      = field(default=False)
    acme_use_wildcard: bool      = field(default=False)
    dns_provider:      str       = field(default="")
    dashboard_enabled: bool      = field(default=False)
    dashboard_domain:  str       = field(default="")
    server_ip:         str       = field(default="")

    @classmethod
    def from_env(cls) -> ProxyDefaults:
        return cls(
            base_domain=os.environ.get("DOOSERVICE_BASE_DOMAIN", ""),
            secondary_domains=json.loads(os.environ.get("DOOSERVICE_SECONDARY_DOMAINS", "[]")),
            acme_email=os.environ.get("DOOSERVICE_ACME_EMAIL", ""),
            acme_staging=bool(os.environ.get("DOOSERVICE_ACME_STAGING")),
            acme_use_wildcard=bool(os.environ.get("DOOSERVICE_ACME_USE_WILDCARD")),
            dns_provider=os.environ.get("DOOSERVICE_DNS_PROVIDER", ""),
            dashboard_enabled=bool(os.environ.get("DOOSERVICE_DASHBOARD_ENABLED")),
            dashboard_domain=os.environ.get("DOOSERVICE_DASHBOARD_DOMAIN", ""),
            server_ip=os.environ.get("DOOSERVICE_SERVER_IP", ""),
        )

    @classmethod
    def from_dict(cls, data: dict) -> ProxyDefaults:
        return cls(
            base_domain=data.get("base_domain", ""),
            secondary_domains=data.get("secondary_domains", []),
            acme_email=data.get("acme_email", ""),
            acme_staging=data.get("acme_staging", False),
            acme_use_wildcard=data.get("acme_use_wildcard", False),
            dns_provider=data.get("dns_provider", ""),
            dashboard_enabled=data.get("dashboard_enabled", False),
            dashboard_domain=data.get("dashboard_domain", ""),
            server_ip=data.get("server_ip", ""),
        )


@dataclass(slots=True)
class PostgresSettings:
    superuser_password:                    str = DEFAULT_PG_SUPERUSER_PASSWORD
    max_connections:                       int = 300
    shared_buffers:                        str = "128MB"
    effective_cache_size:                  str = "512MB"
    work_mem:                              str = "8MB"
    maintenance_work_mem:                  str = "64MB"
    random_page_cost:                      str = "1.1"
    effective_io_concurrency:              int = 200
    wal_compression:                       str = "on"
    checkpoint_completion_target:          str = "0.9"
    max_wal_size:                          str = "2GB"
    min_wal_size:                          str = "512MB"
    autovacuum_max_workers:                int = 4
    autovacuum_naptime:                    str = "30s"
    autovacuum_vacuum_scale_factor:        str = "0.05"
    tcp_keepalives_idle:                   int = 60
    tcp_keepalives_interval:               int = 10
    tcp_keepalives_count:                  int = 6
    idle_in_transaction_session_timeout:   str = "300s"
    idle_session_timeout:                  str = "600s"
    statement_timeout:                     str = "300s"

    @classmethod
    def from_env(cls) -> PostgresSettings:
        return cls(
            superuser_password=os.environ.get("DOOSERVICE_PG_SUPERUSER_PASSWORD", DEFAULT_PG_SUPERUSER_PASSWORD),
            max_connections=int(os.environ.get("DOOSERVICE_PG_MAX_CONNECTIONS", "300")),
            shared_buffers=os.environ.get("DOOSERVICE_PG_SHARED_BUFFERS", "128MB"),
            effective_cache_size=os.environ.get("DOOSERVICE_PG_EFFECTIVE_CACHE_SIZE", "512MB"),
            work_mem=os.environ.get("DOOSERVICE_PG_WORK_MEM", "8MB"),
            maintenance_work_mem=os.environ.get("DOOSERVICE_PG_MAINTENANCE_WORK_MEM", "64MB"),
            random_page_cost=os.environ.get("DOOSERVICE_PG_RANDOM_PAGE_COST", "1.1"),
            effective_io_concurrency=int(os.environ.get("DOOSERVICE_PG_EFFECTIVE_IO_CONCURRENCY", "200")),
            wal_compression=os.environ.get("DOOSERVICE_PG_WAL_COMPRESSION", "on"),
            checkpoint_completion_target=os.environ.get("DOOSERVICE_PG_CHECKPOINT_COMPLETION_TARGET", "0.9"),
            max_wal_size=os.environ.get("DOOSERVICE_PG_MAX_WAL_SIZE", "2GB"),
            min_wal_size=os.environ.get("DOOSERVICE_PG_MIN_WAL_SIZE", "512MB"),
            autovacuum_max_workers=int(os.environ.get("DOOSERVICE_PG_AUTOVACUUM_MAX_WORKERS", "4")),
            autovacuum_naptime=os.environ.get("DOOSERVICE_PG_AUTOVACUUM_NAPTIME", "30s"),
            autovacuum_vacuum_scale_factor=os.environ.get("DOOSERVICE_PG_AUTOVACUUM_VACUUM_SCALE_FACTOR", "0.05"),
            tcp_keepalives_idle=int(os.environ.get("DOOSERVICE_PG_TCP_KEEPALIVES_IDLE", "60")),
            tcp_keepalives_interval=int(os.environ.get("DOOSERVICE_PG_TCP_KEEPALIVES_INTERVAL", "12")),
            tcp_keepalives_count=int(os.environ.get("DOOSERVICE_PG_TCP_KEEPALIVES_COUNT", "6")),
            idle_in_transaction_session_timeout=os.environ.get(
                "DOOSERVICE_PG_IDLE_IN_TRANSACTION_SESSION_TIMEOUT", "300s"
            ),
            idle_session_timeout=os.environ.get("DOOSERVICE_PG_IDLE_SESSION_TIMEOUT", "600s"),
            statement_timeout=os.environ.get("DOOSERVICE_PG_STATEMENT_TIMEOUT", "300s"),
        )

    @classmethod
    def from_dict(cls, data: dict) -> PostgresSettings:
        return cls(
            superuser_password=data.get("superuser_password", DEFAULT_PG_SUPERUSER_PASSWORD),
            max_connections=int(data.get("max_connections", 300)),
            shared_buffers=data.get("shared_buffers", "128MB"),
            effective_cache_size=data.get("effective_cache_size", "512MB"),
            work_mem=data.get("work_mem", "8MB"),
            maintenance_work_mem=data.get("maintenance_work_mem", "64MB"),
            random_page_cost=data.get("random_page_cost", "1.1"),
            effective_io_concurrency=int(data.get("effective_io_concurrency", 200)),
            wal_compression=data.get("wal_compression", "on"),
            checkpoint_completion_target=data.get("checkpoint_completion_target", "0.9"),
            max_wal_size=data.get("max_wal_size", "2GB"),
            min_wal_size=data.get("min_wal_size", "512MB"),
            autovacuum_max_workers=int(data.get("autovacuum_max_workers", 4)),
            autovacuum_naptime=data.get("autovacuum_naptime", "30s"),
            autovacuum_vacuum_scale_factor=data.get("autovacuum_vacuum_scale_factor", "0.05"),
            tcp_keepalives_idle=int(data.get("tcp_keepalives_idle", 60)),
            tcp_keepalives_interval=int(data.get("tcp_keepalives_interval", 10)),
            tcp_keepalives_count=int(data.get("tcp_keepalives_count", 6)),
            idle_in_transaction_session_timeout=data.get("idle_in_transaction_session_timeout", "300s"),
            idle_session_timeout=data.get("idle_session_timeout", "600s"),
            statement_timeout=data.get("statement_timeout", "300s"),
        )


@dataclass(slots=True)
class PgDogSettings:
    workers:              int = 4
    pooler_mode:          str = "session"
    default_pool_size:    int = 10
    maintenance_pool_size: int = 20
    min_pool_size:        int = 1
    connect_timeout:      int = 5000
    checkout_timeout:     int = 10000
    idle_timeout:         int = 300000
    server_lifetime:      int = 3600000

    @classmethod
    def from_env(cls) -> PgDogSettings:
        return cls(
            workers=int(os.environ.get("DOOSERVICE_PGDOG_WORKERS", "4")),
            pooler_mode=os.environ.get("DOOSERVICE_PGDOG_POOLER_MODE", "session"),
            default_pool_size=int(os.environ.get("DOOSERVICE_PGDOG_DEFAULT_POOL_SIZE", "12")),
            maintenance_pool_size=int(os.environ.get("DOOSERVICE_PGDOG_MAINTENANCE_POOL_SIZE", "20")),
            min_pool_size=int(os.environ.get("DOOSERVICE_PGDOG_MIN_POOL_SIZE", "1")),
            connect_timeout=int(os.environ.get("DOOSERVICE_PGDOG_CONNECT_TIMEOUT", "5000")),
            checkout_timeout=int(os.environ.get("DOOSERVICE_PGDOG_CHECKOUT_TIMEOUT", "10000")),
            idle_timeout=int(os.environ.get("DOOSERVICE_PGDOG_IDLE_TIMEOUT", "300000")),
            server_lifetime=int(os.environ.get("DOOSERVICE_PGDOG_SERVER_LIFETIME", "3600000")),
        )

    @classmethod
    def from_dict(cls, data: dict) -> PgDogSettings:
        return cls(
            workers=int(data.get("workers", 4)),
            pooler_mode=data.get("pooler_mode", "session"),
            default_pool_size=int(data.get("default_pool_size", 10)),
            maintenance_pool_size=int(data.get("maintenance_pool_size", 20)),
            min_pool_size=int(data.get("min_pool_size", 1)),
            connect_timeout=int(data.get("connect_timeout", 5000)),
            checkout_timeout=int(data.get("checkout_timeout", 10000)),
            idle_timeout=int(data.get("idle_timeout", 300000)),
            server_lifetime=int(data.get("server_lifetime", 3600000)),
        )


@dataclass(slots=True)
class Config:
    """Agent runtime config. Only `data_dir` is configurable — all subpaths derive from it."""

    data_dir:           Path = DEFAULT_DATA_DIR
    debug:              bool = False
    capture_api_secret: str  = ""
    capture_hostname:   str  = ""
    postgres: PostgresSettings    = field(default_factory=PostgresSettings)
    pgdog:    PgDogSettings       = field(default_factory=PgDogSettings)
    dns:      DnsProviderCredentials = field(default_factory=DnsProviderCredentials)
    proxy:    ProxyDefaults          = field(default_factory=ProxyDefaults)
    s3:       S3Config               = field(default_factory=S3Config)

    # ── Derived paths (read-only, always rooted at data_dir) ────────────────
    @property
    def db_path(self) -> Path:
        return self.data_dir / "agent.db"

    @property
    def pgdog_config_dir(self) -> Path:
        return self.data_dir / "pgdog"

    @property
    def letsencrypt_dir(self) -> Path:
        return self.data_dir / "letsencrypt"

    @property
    def projects_dir(self) -> Path:
        return self.data_dir / "projects"

    @classmethod
    def from_env(cls) -> Config:
        load_dotenv()
        return cls(
            data_dir=Path(os.environ.get("DOOSERVICE_DATA_DIR", DEFAULT_DATA_DIR)),
            debug=bool(os.environ.get("DOOSERVICE_DEBUG")),
            capture_api_secret=os.environ.get("DOOSERVICE_CAPTURE_API_SECRET", ""),
            capture_hostname=os.environ.get("DOOSERVICE_CAPTURE_HOSTNAME", ""),
            postgres=PostgresSettings.from_env(),
            pgdog=PgDogSettings.from_env(),
            dns=DnsProviderCredentials.from_env(),
            proxy=ProxyDefaults.from_env(),
            s3=S3Config.from_env(),
        )

    @classmethod
    def from_dict(cls, data: dict) -> Config:
        return cls(
            data_dir=Path(data.get("data_dir", DEFAULT_DATA_DIR)),
            debug=data.get("debug", False),
            capture_api_secret=data.get("capture_api_secret", ""),
            capture_hostname=data.get("capture_hostname", ""),
            postgres=PostgresSettings.from_dict(data.get("postgres", {})),
            pgdog=PgDogSettings.from_dict(data.get("pgdog", {})),
            dns=DnsProviderCredentials.from_dict(data.get("dns", {})),
            proxy=ProxyDefaults.from_dict(data.get("proxy", {})),
            s3=S3Config.from_dict(data.get("s3", {})),
        )

    @classmethod
    def from_toml(cls, path: Path) -> Config:
        with open(path) as file:
            data = tomlkit.load(file).unwrap()
        return cls.from_dict(data)
