"""Traefik DNS provider adapter: provider name and Traefik env vars per provider."""

from __future__ import annotations

from dooservice_models import (
    OVH,
    CloudflareGlobalKey,
    CloudflareToken,
    DigitalOcean,
    DnsProvider,
    Gandi,
    GoDaddy,
    Hetzner,
    Linode,
    Namecheap,
    Route53,
)


class TraefikDnsProvider:
    """Translates a domain DnsProvider into Traefik's `--dnschallenge.provider`
    name and the matching environment variables Traefik expects.
    """

    @staticmethod
    def name(provider: DnsProvider) -> str:
        match provider:
            case CloudflareToken() | CloudflareGlobalKey():
                return "cloudflare"
            case Route53():
                return "route53"
            case DigitalOcean():
                return "digitalocean"
            case Gandi():
                return "gandiv5"
            case OVH():
                return "ovh"
            case Hetzner():
                return "hetzner"
            case Linode():
                return "linode"
            case GoDaddy():
                return "godaddy"
            case Namecheap():
                return "namecheap"
            case _:
                raise ValueError(f"unsupported DNS provider: {type(provider).__name__}")

    @staticmethod
    def env_vars(provider: DnsProvider) -> dict[str, str]:
        match provider:
            case CloudflareToken(api_token=token):
                return {"CF_DNS_API_TOKEN": token}
            case CloudflareGlobalKey(email=email, api_key=key):
                return {"CF_API_EMAIL": email, "CF_API_KEY": key}
            case Route53(access_key_id=key_id, secret_access_key=secret, region=region, hosted_zone_id=zone):
                env = {"AWS_ACCESS_KEY_ID": key_id, "AWS_SECRET_ACCESS_KEY": secret}
                if region:
                    env["AWS_REGION"] = region
                if zone:
                    env["AWS_HOSTED_ZONE_ID"] = zone
                return env
            case DigitalOcean(api_token=token):
                return {"DO_AUTH_TOKEN": token}
            case Gandi(personal_access_token=token):
                return {"GANDIV5_PERSONAL_ACCESS_TOKEN": token}
            case OVH(endpoint=endpoint, application_key=app_key, application_secret=app_secret, consumer_key=consumer):
                return {
                    "OVH_ENDPOINT": endpoint,
                    "OVH_APPLICATION_KEY": app_key,
                    "OVH_APPLICATION_SECRET": app_secret,
                    "OVH_CONSUMER_KEY": consumer,
                }
            case Hetzner(api_key=api_key):
                return {"HETZNER_API_KEY": api_key}
            case Linode(token=token):
                return {"LINODE_TOKEN": token}
            case GoDaddy(api_key=api_key, api_secret=api_secret):
                return {"GODADDY_API_KEY": api_key, "GODADDY_API_SECRET": api_secret}
            case Namecheap(api_user=api_user, api_key=api_key):
                return {"NAMECHEAP_API_USER": api_user, "NAMECHEAP_API_KEY": api_key}
            case _:
                raise ValueError(f"unsupported DNS provider: {type(provider).__name__}")
