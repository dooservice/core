from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import shutil
import uuid
from uuid import UUID

from dooservice_db_agent import EnvironmentRepository, ProjectRepository
from dooservice_models import (
    Project,
    ProjectHasEnvironmentsError,
    ProjectNameAlreadyExistsError,
)


class ProjectService:
    def __init__(self, projects_dir: Path) -> None:
        self.projects_dir = projects_dir

    @staticmethod
    def build_project(
        name: str,
        *,
        has_repository: bool       = False,
        repo_full_name: str | None = None,
        odoo_version:   str        = "19.0",
        timezone:       str        = "UTC",
        language:       str        = "en_US",
    ) -> Project:
        now = datetime.now(UTC)
        return Project(
            id=uuid.uuid4(),
            name=name,
            has_repository=has_repository,
            repo_full_name=repo_full_name,
            odoo_version=odoo_version,
            timezone=timezone,
            language=language,
            created_at=now,
            updated_at=now,
        )

    async def create(
        self,
        name: str,
        *,
        has_repository: bool       = False,
        repo_full_name: str | None = None,
        odoo_version:   str        = "19.0",
        timezone:       str        = "UTC",
        language:       str        = "en_US",
    ) -> Project:
        project = self.build_project(
            name,
            has_repository=has_repository,
            repo_full_name=repo_full_name,
            odoo_version=odoo_version,
            timezone=timezone,
            language=language,
        )
        if await ProjectRepository.exists_with_name(project.name):
            raise ProjectNameAlreadyExistsError(project.name)
        await ProjectRepository.save(project)
        return project

    async def get(self, name: str) -> Project:
        return await ProjectRepository.get_by_name(name)

    async def get_by_id(self, project_id: UUID) -> Project:
        return await ProjectRepository.get_by_id(project_id)

    async def list_all(self) -> list[Project]:
        return await ProjectRepository.list_all()

    async def delete(self, name: str) -> None:
        project = await ProjectRepository.get_by_name(name)
        if await EnvironmentRepository.has_any_for_project(project.id):
            raise ProjectHasEnvironmentsError(project.name)
        await ProjectRepository.delete(project.id)
        project_dir = self.projects_dir / project.name
        if project_dir.exists():
            shutil.rmtree(project_dir)
