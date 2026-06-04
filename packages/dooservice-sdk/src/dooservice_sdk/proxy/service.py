"""Proxy use cases — configure base domain, TLS, DNS provider; persist."""

from __future__ import annotations

from dooservice_db_agent import ProxyConfigRepository
from dooservice_models import (
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
    ProxyTlsConfig,
    Route53,
)

from ..config import DnsProviderCredentials


class ProxyService:
    async def configure(
        self,
        *,
        base_domain: str,
        acme_email: str = "",
        use_wildcard: bool = False,
        dns_provider: AnyDnsProvider | None = None,
        staging: bool = False,
        dashboard_enabled: bool = False,
        dashboard_domain: str = "",
        server_ip: str = "",
    ) -> ProxyConfig:
        proxy_config = await ProxyConfigRepository.get_or_default()
        proxy_config.base_domain = base_domain.strip().lower().rstrip(".")
        proxy_config.dashboard_enabled = dashboard_enabled
        proxy_config.dashboard_domain = dashboard_domain
        proxy_config.server_ip = server_ip or None
        proxy_config.tls = ProxyTlsConfig(
            enabled=bool(acme_email),
            acme_email=acme_email,
            use_wildcard=use_wildcard,
            dns_provider=dns_provider,
            staging=staging,
        )
        await ProxyConfigRepository.save(proxy_config)
        return proxy_config

    async def get(self) -> ProxyConfig:
        return await ProxyConfigRepository.get_or_default()

    @staticmethod
    def build_provider(kind: str, credentials: DnsProviderCredentials) -> AnyDnsProvider:
        """Build an AnyDnsProvider from a kind + the env-loaded Config credentials."""
        match kind:
            case "cloudflare_token":
                ProxyService.require(credentials.cloudflare_api_token, "DOOSERVICE_CLOUDFLARE_API_TOKEN")
                return CloudflareToken(api_token=credentials.cloudflare_api_token)
            case "cloudflare_global_key":
                ProxyService.require(credentials.cloudflare_email, "DOOSERVICE_CLOUDFLARE_EMAIL")
                ProxyService.require(credentials.cloudflare_global_key, "DOOSERVICE_CLOUDFLARE_GLOBAL_KEY")
                return CloudflareGlobalKey(
                    email=credentials.cloudflare_email,
                    api_key=credentials.cloudflare_global_key,
                )
            case "route53":
                ProxyService.require(credentials.route53_access_key_id, "DOOSERVICE_ROUTE53_ACCESS_KEY_ID")
                ProxyService.require(credentials.route53_secret_access_key, "DOOSERVICE_ROUTE53_SECRET_ACCESS_KEY")
                return Route53(
                    access_key_id=credentials.route53_access_key_id,
                    secret_access_key=credentials.route53_secret_access_key,
                    region=credentials.route53_region or None,
                    hosted_zone_id=credentials.route53_hosted_zone_id or None,
                )
            case "digitalocean":
                ProxyService.require(credentials.digitalocean_api_token, "DOOSERVICE_DIGITALOCEAN_API_TOKEN")
                return DigitalOcean(api_token=credentials.digitalocean_api_token)
            case "gandi":
                ProxyService.require(credentials.gandi_personal_access_token, "DOOSERVICE_GANDI_PERSONAL_ACCESS_TOKEN")
                return Gandi(personal_access_token=credentials.gandi_personal_access_token)
            case "ovh":
                ProxyService.require(credentials.ovh_endpoint, "DOOSERVICE_OVH_ENDPOINT")
                ProxyService.require(credentials.ovh_application_key, "DOOSERVICE_OVH_APPLICATION_KEY")
                ProxyService.require(credentials.ovh_application_secret, "DOOSERVICE_OVH_APPLICATION_SECRET")
                ProxyService.require(credentials.ovh_consumer_key, "DOOSERVICE_OVH_CONSUMER_KEY")
                return OVH(
                    endpoint=credentials.ovh_endpoint,
                    application_key=credentials.ovh_application_key,
                    application_secret=credentials.ovh_application_secret,
                    consumer_key=credentials.ovh_consumer_key,
                )
            case "hetzner":
                ProxyService.require(credentials.hetzner_api_key, "DOOSERVICE_HETZNER_API_KEY")
                return Hetzner(api_key=credentials.hetzner_api_key)
            case "linode":
                ProxyService.require(credentials.linode_token, "DOOSERVICE_LINODE_TOKEN")
                return Linode(token=credentials.linode_token)
            case "godaddy":
                ProxyService.require(credentials.godaddy_api_key, "DOOSERVICE_GODADDY_API_KEY")
                ProxyService.require(credentials.godaddy_api_secret, "DOOSERVICE_GODADDY_API_SECRET")
                return GoDaddy(api_key=credentials.godaddy_api_key, api_secret=credentials.godaddy_api_secret)
            case "namecheap":
                ProxyService.require(credentials.namecheap_api_user, "DOOSERVICE_NAMECHEAP_API_USER")
                ProxyService.require(credentials.namecheap_api_key, "DOOSERVICE_NAMECHEAP_API_KEY")
                return Namecheap(api_user=credentials.namecheap_api_user, api_key=credentials.namecheap_api_key)
            case _:
                raise ValueError(f"unsupported DNS provider kind: {kind!r}")

    @staticmethod
    def require(value: str, env_var_name: str) -> None:
        if not value:
            raise ValueError(f"{env_var_name} is required for this DNS provider")
