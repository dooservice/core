"""Domain errors raised by repositories and services."""

from __future__ import annotations


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


class ProjectNotFoundError(NotFoundError):
    def __init__(self, identifier: str = "") -> None:
        super().__init__(f"project '{identifier}' not found" if identifier else "project not found")


class EnvironmentNotFoundError(NotFoundError):
    def __init__(self, identifier: str = "") -> None:
        super().__init__(f"environment '{identifier}' not found" if identifier else "environment not found")


class ProjectNameAlreadyExistsError(ConflictError):
    def __init__(self, name: str = "") -> None:
        super().__init__(f"project '{name}' already exists" if name else "project already exists")


class ProjectHasEnvironmentsError(ConflictError):
    def __init__(self, name: str = "") -> None:
        msg = (
            f"project '{name}' still has environments; delete them first" if name else "project still has environments"
        )
        super().__init__(msg)


class EnvironmentAlreadyExistsError(ConflictError):
    def __init__(self, identifier: str = "") -> None:
        super().__init__(f"environment '{identifier}' already exists" if identifier else "environment already exists")


class CustomDomainAlreadyExistsError(ConflictError):
    def __init__(self, domain: str = "") -> None:
        super().__init__(f"custom domain '{domain}' already attached" if domain else "custom domain already attached")


class CustomDomainNotFoundError(NotFoundError):
    def __init__(self, domain: str = "") -> None:
        super().__init__(f"custom domain '{domain}' not found" if domain else "custom domain not found")


class ProxyConfigNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("proxy config not initialised — run `doos proxy configure` first")


class DeploymentNotFoundError(NotFoundError):
    def __init__(self, environment_id: object, revision: int) -> None:
        super().__init__(f"deployment revision {revision} not found for environment {environment_id}")
