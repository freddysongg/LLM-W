from __future__ import annotations


class ProjectNotFoundError(Exception):
    def __init__(self, project_id: str) -> None:
        super().__init__(f"Project not found: {project_id}")
        self.project_id = project_id


class ProjectNameConflictError(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(f"Project name already exists: {name}")
        self.name = name


class ConfigVersionNotFoundError(Exception):
    def __init__(self, version_id: str) -> None:
        super().__init__(f"Config version not found: {version_id}")
        self.version_id = version_id


class ConfigValidationError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
