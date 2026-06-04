from __future__ import annotations

from uuid import UUID

from dooservice_models import Project, ProjectNameAlreadyExistsError, ProjectNotFoundError

from ..models import ProjectModel


class ProjectRepository:
    @staticmethod
    async def get_by_id(project_id: UUID) -> Project:
        model = await ProjectModel.get_or_none(id=project_id)
        if model is None:
            raise ProjectNotFoundError(str(project_id))
        return model.to_struct()

    @staticmethod
    async def get_by_name(name: str) -> Project:
        model = await ProjectModel.get_or_none(name=name)
        if model is None:
            raise ProjectNotFoundError(name)
        return model.to_struct()

    @staticmethod
    async def exists_with_name(name: str) -> bool:
        return await ProjectModel.exists(name=name)

    @staticmethod
    async def list_all() -> list[Project]:
        models = await ProjectModel.all().order_by("-created_at")
        return [m.to_struct() for m in models]

    @staticmethod
    async def save(project: Project) -> None:
        if await ProjectModel.exists(name=project.name):
            raise ProjectNameAlreadyExistsError(project.name)
        await ProjectModel.from_struct(project).save()

    @staticmethod
    async def delete(project_id: UUID) -> None:
        if not await ProjectModel.exists(id=project_id):
            raise ProjectNotFoundError(str(project_id))
        await ProjectModel.filter(id=project_id).delete()
