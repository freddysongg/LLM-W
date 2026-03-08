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


class ModelNotResolvedError(Exception):
    def __init__(self, project_id: str) -> None:
        super().__init__(f"No model resolved for project: {project_id}")
        self.project_id = project_id


class ModelResolveError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class LayerNotFoundError(Exception):
    def __init__(self, layer_name: str) -> None:
        super().__init__(f"Layer not found: {layer_name}")
        self.layer_name = layer_name


class ActivationSnapshotNotFoundError(Exception):
    def __init__(self, snapshot_id: str) -> None:
        super().__init__(f"Activation snapshot not found: {snapshot_id}")
        self.snapshot_id = snapshot_id


class DatasetNotResolvedError(Exception):
    def __init__(self, project_id: str) -> None:
        super().__init__(f"No dataset resolved for project: {project_id}")
        self.project_id = project_id


class DatasetResolveError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class CheckpointNotFoundError(Exception):
    def __init__(self, path: str) -> None:
        super().__init__(f"Checkpoint not found: {path}")
        self.path = path
