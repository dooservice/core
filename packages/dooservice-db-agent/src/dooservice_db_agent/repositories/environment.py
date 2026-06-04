from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import msgspec

from dooservice_models import (
    Environment,
    EnvironmentAlreadyExistsError,
    EnvironmentConfig,
    EnvironmentMode,
    EnvironmentNotFoundError,
    LifecycleState,
    RuntimeState,
)

from ..models import EnvironmentModel


class EnvironmentRepository:
    @staticmethod
    async def get(environment_id: UUID) -> Environment:
        model = await EnvironmentModel.get_or_none(id=environment_id)
        if model is None:
            raise EnvironmentNotFoundError(str(environment_id))
        return model.to_struct()

    @staticmethod
    async def list_for_project(project_id: UUID) -> list[Environment]:
        models = await EnvironmentModel.filter(project_id=project_id).order_by("-created_at")
        return [m.to_struct() for m in models]

    @staticmethod
    async def list_all() -> list[Environment]:
        models = await EnvironmentModel.all()
        return [m.to_struct() for m in models]

    @staticmethod
    async def exists_with_name(project_id: UUID, name: str) -> bool:
        return await EnvironmentModel.exists(project_id=project_id, name=name)

    @staticmethod
    async def production_exists(project_id: UUID) -> bool:
        return await EnvironmentModel.exists(project_id=project_id, mode=EnvironmentMode.PRODUCTION)

    @staticmethod
    async def has_any_for_project(project_id: UUID) -> bool:
        return await EnvironmentModel.exists(project_id=project_id)

    @staticmethod
    async def save(env: Environment) -> None:
        if await EnvironmentModel.exists(id=env.id):
            raise EnvironmentAlreadyExistsError(str(env.id))
        await EnvironmentModel.from_struct(env).save()

    @staticmethod
    async def update_runtime_state(environment_id: UUID, state: RuntimeState) -> None:
        if not await EnvironmentModel.exists(id=environment_id):
            raise EnvironmentNotFoundError(str(environment_id))
        await EnvironmentModel.filter(id=environment_id).update(
            runtime_state=state,
            updated_at=datetime.now(UTC),
        )

    @staticmethod
    async def update_lifecycle_state(environment_id: UUID, state: LifecycleState) -> None:
        if not await EnvironmentModel.exists(id=environment_id):
            raise EnvironmentNotFoundError(str(environment_id))
        await EnvironmentModel.filter(id=environment_id).update(
            lifecycle_state=state,
            updated_at=datetime.now(UTC),
        )

    @staticmethod
    async def update_container_id(environment_id: UUID, container_id: str) -> None:
        if not await EnvironmentModel.exists(id=environment_id):
            raise EnvironmentNotFoundError(str(environment_id))
        await EnvironmentModel.filter(id=environment_id).update(
            container_id=container_id,
            updated_at=datetime.now(UTC),
        )

    @staticmethod
    async def update_config(environment_id: UUID, config: EnvironmentConfig) -> None:
        if not await EnvironmentModel.exists(id=environment_id):
            raise EnvironmentNotFoundError(str(environment_id))
        await EnvironmentModel.filter(id=environment_id).update(
            config=msgspec.to_builtins(config),
            updated_at=datetime.now(UTC),
        )

    @staticmethod
    async def update_git(environment_id: UUID, branch: str | None = None, commit: str | None = None) -> None:
        updates: dict = {"updated_at": datetime.now(UTC)}
        if branch is not None:
            updates["branch"] = branch
        if commit is not None:
            updates["commit"] = commit
        await EnvironmentModel.filter(id=environment_id).update(**updates)

    @staticmethod
    async def delete(environment_id: UUID) -> None:
        if not await EnvironmentModel.exists(id=environment_id):
            raise EnvironmentNotFoundError(str(environment_id))
        await EnvironmentModel.filter(id=environment_id).delete()
