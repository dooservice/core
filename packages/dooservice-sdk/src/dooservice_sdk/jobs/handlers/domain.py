from __future__ import annotations

from uuid import UUID

import msgspec

from dooservice_models import CustomDomainStatus
from dooservice_protocol import DomainRemoveArgs, DomainSetArgs, DomainVerifyArgs as VerifyArgs

from ..context import JobContext


class DomainSet:
    async def run(self, ctx: JobContext) -> dict:
        args = msgspec.convert(ctx.args, DomainSetArgs)
        env  = await ctx.sdk.domains.set_domain(UUID(args.environment_id), args.domain)
        cd   = env.config.custom_domain
        return {"custom_domain": msgspec.to_builtins(cd) if cd else None}


class DomainRemove:
    async def run(self, ctx: JobContext) -> dict:
        args           = msgspec.convert(ctx.args, DomainRemoveArgs)
        environment_id = UUID(args.environment_id)
        await ctx.progress("Removing custom domain", 0)
        await ctx.sdk.domains.remove_domain(environment_id)
        await ctx.progress("Applying routing changes", 60)
        await ctx.sdk.environments.update_routing(environment_id)
        return {"removed": True}


class DomainVerify:
    async def run(self, ctx: JobContext) -> dict:
        args   = msgspec.convert(ctx.args, VerifyArgs)
        env_id = UUID(args.environment_id)

        env_before   = await ctx.sdk.environments.get(env_id)
        was_verified = (
            env_before.config.custom_domain is not None
            and env_before.config.custom_domain.status == CustomDomainStatus.VERIFIED
        )

        env = await ctx.sdk.domains.verify_domain(env_id)
        cd  = env.config.custom_domain

        newly_verified = cd is not None and cd.status == CustomDomainStatus.VERIFIED and not was_verified
        if newly_verified:
            await ctx.progress("Applying routing changes", 60)
            await ctx.sdk.environments.update_routing(env_id)

        return {"verified": cd is not None, "custom_domain": msgspec.to_builtins(cd) if cd else None}
