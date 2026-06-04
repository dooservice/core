"""Domain use cases — primary domain sync and custom domain lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from dooservice_db_agent import EnvironmentRepository, ProxyConfigRepository
from dooservice_dns import DnsManager, NoopDnsManager, verify_cname_record
from dooservice_models import (
    CustomDomain,
    CustomDomainAlreadyExistsError,
    CustomDomainNotFoundError,
    CustomDomainStatus,
    Environment,
)


class DomainService:
    def __init__(self, dns_manager: DnsManager | None = None) -> None:
        self.dns_manager = dns_manager or NoopDnsManager()

    async def sync_primary(self, environment_id: UUID) -> Environment:
        environment = await EnvironmentRepository.get(environment_id)
        proxy = await ProxyConfigRepository.get()
        environment.config.primary_domain = proxy.primary_domain_for(environment.name)
        environment.config.proxy_network_name = proxy.network_name
        await EnvironmentRepository.update_config(environment.id, environment.config)
        return environment

    async def set_domain(self, environment_id: UUID, domain: str) -> Environment:
        environment = await EnvironmentRepository.get(environment_id)
        normalized = self.normalize(domain)
        if environment.config.custom_domain is not None:
            raise CustomDomainAlreadyExistsError(environment.config.custom_domain.domain)
        await self.dns_manager.ensure_record(normalized, environment.config.primary_domain)
        environment.config.custom_domain = CustomDomain(
            domain=normalized,
            status=CustomDomainStatus.PENDING,
            expected_target=environment.config.primary_domain,
        )
        await EnvironmentRepository.update_config(environment.id, environment.config)
        return environment

    async def remove_domain(self, environment_id: UUID) -> Environment:
        environment = await EnvironmentRepository.get(environment_id)
        if environment.config.custom_domain is None:
            raise CustomDomainNotFoundError()
        await self.dns_manager.remove_record(environment.config.custom_domain.domain)
        environment.config.custom_domain = None
        await EnvironmentRepository.update_config(environment.id, environment.config)
        return environment

    async def verify_domain(self, environment_id: UUID) -> Environment:
        environment = await EnvironmentRepository.get(environment_id)
        entry = environment.config.custom_domain
        if entry is None:
            raise CustomDomainNotFoundError()
        result = await verify_cname_record(entry.domain, entry.expected_target or environment.config.primary_domain)
        now = datetime.now(UTC)
        entry.last_checked_at = now
        entry.updated_at = now
        if result.verified:
            entry.status = CustomDomainStatus.VERIFIED
            entry.verification_error = None
            entry.verified_at = now
        else:
            entry.status = CustomDomainStatus.FAILED
            entry.verification_error = result.reason
        await EnvironmentRepository.update_config(environment.id, environment.config)
        return environment

    async def get_domain(self, environment_id: UUID) -> CustomDomain | None:
        environment = await EnvironmentRepository.get(environment_id)
        return environment.config.custom_domain

    @staticmethod
    def normalize(domain: str) -> str:
        return domain.strip().lower().rstrip(".")
