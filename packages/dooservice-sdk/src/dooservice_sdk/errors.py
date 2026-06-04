"""Domain errors raised by the core service layer."""

from __future__ import annotations


class CoreError(Exception):
    """Base class for all errors surfaced by the core layer."""


class DuplicateProductionEnvironmentError(CoreError):
    def __init__(self) -> None:
        super().__init__("project already has a production environment")


class DatabaseInitializationFailedError(CoreError):
    def __init__(self, exit_code: int, output: str) -> None:
        self.exit_code = exit_code
        self.output = output
        super().__init__(f"db init failed (exit {exit_code}): {output}")


class BackupFailedError(CoreError):
    def __init__(self, output: str) -> None:
        super().__init__(f"Backup failed: {output}")


class RestoreFailedError(CoreError):
    def __init__(self, output: str) -> None:
        super().__init__(f"Restore failed: {output}")


class BackupNotFoundError(CoreError):
    def __init__(self, backup_id) -> None:
        super().__init__(f"Backup {backup_id} not found")


class BackupNotDownloadableError(CoreError):
    def __init__(self, resource_id) -> None:
        super().__init__(f"Backup {resource_id} is not stored in S3 and cannot be downloaded")


class CloneFailedError(CoreError):
    def __init__(self, step: str, output: str) -> None:
        super().__init__(f"Clone failed at {step}: {output}")


class NeutralizeFailedError(CoreError):
    def __init__(self, step: str, output: str) -> None:
        super().__init__(f"Neutralize failed at {step}: {output}")


class SubmoduleMissingKeyError(CoreError):
    def __init__(self, urls: list[str]) -> None:
        listed = "\n  ".join(urls)
        super().__init__(
            f"deploy key not configured for submodule(s):\n  {listed}\n"
            "Add a deploy key for each submodule via the project settings."
        )


class CommitNotFoundError(CoreError):
    def __init__(self, commit_sha: str) -> None:
        super().__init__(f"commit {commit_sha!r} not found in local repository")


class InvalidBackupObjectKeyError(CoreError):
    def __init__(self, object_key: str, environment_name: str) -> None:
        super().__init__(
            f"object key {object_key!r} does not belong to environment {environment_name!r}"
        )
