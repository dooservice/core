"""Database lifecycle: init_db / close_db."""

from __future__ import annotations

from tortoise import Tortoise

from dooservice_models import MODELS_MODULE


async def init_db(db_url: str = "sqlite://agent.db") -> None:
    await Tortoise.init(db_url=db_url, modules={"models": [MODELS_MODULE]})
    await Tortoise.generate_schemas(safe=True)


async def close_db() -> None:
    await Tortoise.close_connections()
