"""ProxyConfig repository — singleton row (id=1) holding the active proxy config."""

from __future__ import annotations

import msgspec

from dooservice_models import ProxyConfig, ProxyConfigNotFoundError

from ..models import ProxyConfigModel


class ProxyConfigRepository:
    @staticmethod
    async def get() -> ProxyConfig:
        model = await ProxyConfigModel.get_or_none(id=1)
        if model is None:
            raise ProxyConfigNotFoundError()
        return model.to_struct()

    @staticmethod
    async def get_or_default() -> ProxyConfig:
        model = await ProxyConfigModel.get_or_none(id=1)
        return model.to_struct() if model else ProxyConfig()

    @staticmethod
    async def exists() -> bool:
        return await ProxyConfigModel.exists(id=1)

    @staticmethod
    async def save(proxy_config: ProxyConfig) -> None:
        existing = await ProxyConfigModel.get_or_none(id=1)
        if existing is None:
            await ProxyConfigModel.from_struct(proxy_config).save()
            return
        existing.payload = msgspec.to_builtins(proxy_config)
        await existing.save()

    @staticmethod
    async def delete() -> None:
        await ProxyConfigModel.filter(id=1).delete()
