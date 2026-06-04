"""Lifecycle management for the shared infrastructure containers."""

from __future__ import annotations

from dooservice_db_agent import ProxyConfigRepository
from dooservice_dns import DnsManager
from dooservice_docker import DockerClient
from dooservice_models import (
    DOOSERVICE_NETWORK_NAME,
    OVH,
    AnyDnsProvider,
    CloudflareGlobalKey,
    CloudflareToken,
    DigitalOcean,
    Gandi,
    GoDaddy,
    Hetzner,
    Linode,
    Namecheap,
    ProxyConfig,
    ProxyStatus,
    ProxyTlsConfig,
    Route53,
)

from ..config import Config, DnsProviderCredentials
from .capture import CaptureService
from .pgdog import PgDogService
from .postgres import SharedPostgresService
from .service_status import ServiceStatus
from .traefik import TraefikProxyService


class Bootstrap:
    """Brings the full shared-infra stack up, down, or destroys it.

    Also owns the configure() use case: building the DNS provider from a kind
    string, assembling the ProxyConfig, and persisting it. This is a one-time
    setup operation that logically belongs to bootstrapping the VPS, not to
    ongoing proxy container management.
    """

    def __init__(
        self,
        docker: DockerClient,
        config: Config,
        proxy_config: ProxyConfig,
        dns_manager: DnsManager,
        network_name: str = DOOSERVICE_NETWORK_NAME,
    ) -> None:
        self.docker       = docker
        self.config       = config
        self.proxy_config = proxy_config
        self.dns_manager  = dns_manager
        self.network_name = network_name
        self.postgres = SharedPostgresService(docker, config.postgres, network_name)
        self.pgdog    = PgDogService(docker, config.pgdog_config_dir, config.pgdog, network_name)
        self.proxy    = TraefikProxyService(docker, proxy_config, config.letsencrypt_dir)
        self.capture  = CaptureService(
            docker,
            network_name=network_name,
            proxy_network_name=proxy_config.network_name,
            base_domain=proxy_config.base_domain,
            api_secret=config.capture_api_secret,
            hostname=config.capture_hostname,
            tls_enabled=proxy_config.tls.enabled,
        )

    async def configure(
        self,
        *,
        base_domain:        str | None       = None,
        secondary_domains:  list[str] | None = None,
        acme_email:         str | None       = None,
        use_wildcard:       bool | None      = None,
        staging:            bool | None      = None,
        dashboard_enabled:  bool | None      = None,
        dashboard_domain:   str | None       = None,
        dns_provider_kind:  str | None       = None,
        server_ip:          str | None       = None,
    ) -> ProxyConfig:
        """Configure the proxy base domain, TLS and DNS provider, and persist to DB.

        Any None argument falls back to the value from self.config.proxy (loaded
        from the agent TOML or DOOSERVICE_* environment variables). Raises
        ValueError if base_domain is still empty after resolution, or if
        dns_provider_kind is unrecognised or its required credentials are missing.
        """
        defaults = self.config.proxy

        resolved_base_domain      = base_domain       if base_domain       is not None else defaults.base_domain
        resolved_secondary_domains = secondary_domains if secondary_domains is not None else defaults.secondary_domains
        resolved_acme_email       = acme_email        if acme_email        is not None else defaults.acme_email
        resolved_use_wildcard     = use_wildcard      if use_wildcard      is not None else defaults.acme_use_wildcard
        resolved_staging          = staging           if staging           is not None else defaults.acme_staging
        resolved_dashboard        = dashboard_enabled if dashboard_enabled is not None else defaults.dashboard_enabled
        resolved_dash_domain      = dashboard_domain  if dashboard_domain  is not None else defaults.dashboard_domain
        resolved_provider_kind    = dns_provider_kind if dns_provider_kind is not None else defaults.dns_provider
        resolved_server_ip        = server_ip         if server_ip         is not None else defaults.server_ip

        if not resolved_base_domain:
            raise ValueError("base_domain is required (pass --base-domain or set DOOSERVICE_BASE_DOMAIN)")

        provider = (
            self.build_dns_provider(resolved_provider_kind, self.config.dns)
            if resolved_provider_kind
            else None
        )

        proxy_config = await ProxyConfigRepository.get_or_default()
        proxy_config.base_domain       = resolved_base_domain
        proxy_config.secondary_domains = resolved_secondary_domains
        proxy_config.dashboard_enabled = resolved_dashboard
        proxy_config.dashboard_domain  = resolved_dash_domain
        proxy_config.server_ip         = resolved_server_ip or None
        proxy_config.tls = ProxyTlsConfig(
            enabled=bool(resolved_acme_email),
            acme_email=resolved_acme_email,
            use_wildcard=resolved_use_wildcard,
            dns_provider=provider,
            staging=resolved_staging,
        )
        await ProxyConfigRepository.save(proxy_config)
        return proxy_config

    @staticmethod
    def build_dns_provider(kind: str, credentials: DnsProviderCredentials) -> AnyDnsProvider:
        """Instantiate an AnyDnsProvider from a kind string and credential config.

        Raises ValueError for unrecognised kind or missing required credentials.
        """
        def require(value: str, env_var: str) -> None:
            if not value:
                raise ValueError(f"{env_var} is required for DNS provider '{kind}'")

        match kind:
            case "cloudflare_token":
                require(credentials.cloudflare_api_token, "DOOSERVICE_CLOUDFLARE_API_TOKEN")
                return CloudflareToken(api_token=credentials.cloudflare_api_token)
            case "cloudflare_global_key":
                require(credentials.cloudflare_email, "DOOSERVICE_CLOUDFLARE_EMAIL")
                require(credentials.cloudflare_global_key, "DOOSERVICE_CLOUDFLARE_GLOBAL_KEY")
                return CloudflareGlobalKey(
                    email=credentials.cloudflare_email,
                    api_key=credentials.cloudflare_global_key,
                )
            case "route53":
                require(credentials.route53_access_key_id, "DOOSERVICE_ROUTE53_ACCESS_KEY_ID")
                require(credentials.route53_secret_access_key, "DOOSERVICE_ROUTE53_SECRET_ACCESS_KEY")
                return Route53(
                    access_key_id=credentials.route53_access_key_id,
                    secret_access_key=credentials.route53_secret_access_key,
                    region=credentials.route53_region or None,
                    hosted_zone_id=credentials.route53_hosted_zone_id or None,
                )
            case "digitalocean":
                require(credentials.digitalocean_api_token, "DOOSERVICE_DIGITALOCEAN_API_TOKEN")
                return DigitalOcean(api_token=credentials.digitalocean_api_token)
            case "gandi":
                require(credentials.gandi_personal_access_token, "DOOSERVICE_GANDI_PERSONAL_ACCESS_TOKEN")
                return Gandi(personal_access_token=credentials.gandi_personal_access_token)
            case "ovh":
                require(credentials.ovh_endpoint,           "DOOSERVICE_OVH_ENDPOINT")
                require(credentials.ovh_application_key,    "DOOSERVICE_OVH_APPLICATION_KEY")
                require(credentials.ovh_application_secret, "DOOSERVICE_OVH_APPLICATION_SECRET")
                require(credentials.ovh_consumer_key,       "DOOSERVICE_OVH_CONSUMER_KEY")
                return OVH(
                    endpoint=credentials.ovh_endpoint,
                    application_key=credentials.ovh_application_key,
                    application_secret=credentials.ovh_application_secret,
                    consumer_key=credentials.ovh_consumer_key,
                )
            case "hetzner":
                require(credentials.hetzner_api_key, "DOOSERVICE_HETZNER_API_KEY")
                return Hetzner(api_key=credentials.hetzner_api_key)
            case "linode":
                require(credentials.linode_token, "DOOSERVICE_LINODE_TOKEN")
                return Linode(token=credentials.linode_token)
            case "godaddy":
                require(credentials.godaddy_api_key,    "DOOSERVICE_GODADDY_API_KEY")
                require(credentials.godaddy_api_secret, "DOOSERVICE_GODADDY_API_SECRET")
                return GoDaddy(api_key=credentials.godaddy_api_key, api_secret=credentials.godaddy_api_secret)
            case "namecheap":
                require(credentials.namecheap_api_user, "DOOSERVICE_NAMECHEAP_API_USER")
                require(credentials.namecheap_api_key,  "DOOSERVICE_NAMECHEAP_API_KEY")
                return Namecheap(api_user=credentials.namecheap_api_user, api_key=credentials.namecheap_api_key)
            case _:
                raise ValueError(f"unsupported DNS provider kind: {kind!r}")

    async def ensure_running(self) -> None:
        await self.docker.ensure_network(self.network_name)
        await self.postgres.ensure_running()
        await self.pgdog.ensure_running()
        await self.proxy.ensure_running()
        await self.capture.ensure_running()
        if self.proxy_config.server_ip and self.capture.domain:
            await self.dns_manager.ensure_record(self.capture.domain, self.proxy_config.server_ip)

    async def stop(self) -> None:
        await self.capture.stop()
        await self.proxy.stop()
        await self.pgdog.stop()
        await self.postgres.stop()

    async def destroy(self) -> None:
        await self.capture.destroy()
        await self.proxy.destroy()
        await self.pgdog.destroy()
        await self.postgres.destroy()

    async def status(self) -> tuple[ServiceStatus, ServiceStatus, ProxyStatus, ServiceStatus]:
        pg_status      = await self.postgres.status()
        pgdog_status   = await self.pgdog.status()
        proxy_status   = await self.proxy.status()
        capture_status = await self.capture.status()
        return pg_status, pgdog_status, proxy_status, capture_status
