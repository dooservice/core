from __future__ import annotations

from uuid import UUID

from dooservice_models import DeploymentNotFoundError, DeploymentStatus, EnvironmentDeployment

from ..models import EnvironmentDeploymentModel


class DeploymentRepository:
    @staticmethod
    async def save(deployment: EnvironmentDeployment) -> None:
        await EnvironmentDeploymentModel.create(
            id=deployment.id,
            environment_id=deployment.environment_id,
            revision=deployment.revision,
            triggered_by=deployment.triggered_by,
            commit_before=deployment.commit_before,
            commit_after=deployment.commit_after,
            branch=deployment.branch,
            config_snapshot=deployment.config_snapshot,
            backup_id=deployment.backup_id,
            status=deployment.status.value,
        )

    @staticmethod
    async def next_revision(environment_id: UUID) -> int:
        last = await EnvironmentDeploymentModel.filter(
            environment_id=environment_id,
        ).order_by("-revision").first()
        return (last.revision + 1) if last else 1

    @staticmethod
    async def get_revision(environment_id: UUID, revision: int) -> EnvironmentDeployment:
        row = await EnvironmentDeploymentModel.get_or_none(
            environment_id=environment_id,
            revision=revision,
        )
        if row is None:
            raise DeploymentNotFoundError(environment_id, revision)
        return row.to_struct()

    @staticmethod
    async def list_for_environment(environment_id: UUID) -> list[EnvironmentDeployment]:
        rows = await EnvironmentDeploymentModel.filter(
            environment_id=environment_id,
        ).order_by("-revision")
        return [row.to_struct() for row in rows]

    @staticmethod
    async def update_status(
        deployment_id: UUID,
        status: DeploymentStatus,
        *,
        commit_after: str | None = None,
    ) -> None:
        updates: dict = {"status": status.value}
        if commit_after is not None:
            updates["commit_after"] = commit_after
        await EnvironmentDeploymentModel.filter(id=deployment_id).update(**updates)

    @staticmethod
    async def drop_previous(environment_id: UUID, revision: int) -> None:
        """Mark all revisions older than `revision` as dropped (superseded by new deploy)."""
        await EnvironmentDeploymentModel.filter(
            environment_id=environment_id,
            revision__lt=revision,
        ).exclude(status=DeploymentStatus.DROPPED.value).update(
            status=DeploymentStatus.DROPPED.value,
        )

    @staticmethod
    async def drop_after_revision(environment_id: UUID, revision: int) -> list[UUID]:
        """Mark all revisions newer than `revision` as dropped. Returns their backup_ids."""
        rows = await EnvironmentDeploymentModel.filter(
            environment_id=environment_id,
            revision__gt=revision,
        ).all()
        backup_ids = [row.backup_id for row in rows if row.backup_id is not None]
        await EnvironmentDeploymentModel.filter(
            environment_id=environment_id,
            revision__gt=revision,
        ).update(status=DeploymentStatus.DROPPED.value)
        return backup_ids
