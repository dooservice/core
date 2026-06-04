"""Deployment history — snapshot of environment state captured before each git.pull."""

from __future__ import annotations

from enum import StrEnum
import uuid

import msgspec


class DeploymentStatus(StrEnum):
    SUCCESS     = "success"
    FAILED      = "failed"
    ROLLED_BACK = "rolled_back"
    DROPPED     = "dropped"


class EnvironmentDeployment(msgspec.Struct):
    id:              uuid.UUID
    environment_id:  uuid.UUID
    revision:        int
    triggered_by:    str
    commit_before:   str | None
    commit_after:    str | None
    branch:          str | None
    config_snapshot: dict
    backup_id:       uuid.UUID | None
    status:          DeploymentStatus
    created_at:      str = ""
