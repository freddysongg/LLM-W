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


class DatasetNormalizationError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class DatasetSanitizationError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class RunNotFoundError(Exception):
    def __init__(self, run_id: str) -> None:
        super().__init__(f"Run not found: {run_id}")
        self.run_id = run_id


class RunStateError(Exception):
    def __init__(self, *, run_id: str, action: str, current_status: str) -> None:
        super().__init__(f"Cannot {action} run {run_id}: current status is {current_status}")
        self.run_id = run_id
        self.action = action
        self.current_status = current_status


class NoCheckpointError(Exception):
    def __init__(self, run_id: str) -> None:
        super().__init__(f"No valid checkpoint found for run: {run_id}")
        self.run_id = run_id


class ModalResumeUnsupportedError(Exception):
    def __init__(self, run_id: str) -> None:
        super().__init__(
            "Resuming a Modal-trained run is not supported: each Modal sandbox "
            "uses a per-run Volume that does not mount the parent run's "
            f"checkpoint (parent run: {run_id}). Start a fresh run instead."
        )
        self.run_id = run_id


class CheckpointNotFoundError(Exception):
    def __init__(self, checkpoint_id: str) -> None:
        super().__init__(f"Checkpoint not found: {checkpoint_id}")
        self.checkpoint_id = checkpoint_id


class SuggestionNotFoundError(Exception):
    def __init__(self, suggestion_id: str) -> None:
        super().__init__(f"Suggestion not found: {suggestion_id}")
        self.suggestion_id = suggestion_id


class ArtifactNotFoundError(Exception):
    def __init__(self, artifact_id: str) -> None:
        super().__init__(f"Artifact not found: {artifact_id}")
        self.artifact_id = artifact_id


class ArtifactFileNotFoundError(Exception):
    def __init__(self, artifact_id: str) -> None:
        super().__init__(f"Artifact file not found on disk: {artifact_id}")
        self.artifact_id = artifact_id


class VoiceCredentialsMissingError(Exception):
    """Raised when a voice session is requested but provider keys are unset."""

    def __init__(self, *, missing: list[str]) -> None:
        super().__init__(
            "Voice session cannot start: missing provider credentials "
            f"({', '.join(missing)}). Configure them via /api/v1/settings."
        )
        self.missing = missing


class VoicePipecatNotInstalledError(Exception):
    """Raised when pipecat-ai is not installed but a voice session is started."""

    def __init__(self) -> None:
        super().__init__(
            "Voice session requires the pipecat-ai optional dependency. "
            "Install with 'pip install -e \".[voice]\"' to enable voice routes."
        )


class VoiceSessionAlreadyActiveError(Exception):
    """Raised when a second concurrent voice session is requested."""

    def __init__(self, *, active_session_id: str) -> None:
        super().__init__(f"Voice session already active: {active_session_id}")
        self.active_session_id = active_session_id


class VoiceSessionNotFoundError(Exception):
    """Raised when a websocket connects with an unknown session id."""

    def __init__(self, session_id: str) -> None:
        super().__init__(f"Voice session not found: {session_id}")
        self.session_id = session_id


class NotificationNotFoundError(Exception):
    def __init__(self, notification_id: str) -> None:
        super().__init__(f"Notification not found: {notification_id}")
        self.notification_id = notification_id


class MissingServingModelIdError(Exception):
    """Raised when a serve request omits serving_model_id and the project config has none."""

    def __init__(self, project_id: str) -> None:
        super().__init__(
            f"Project {project_id} has no serving_model_id configured and the "
            "request did not supply one. Set model.serving_model_id in the YAML "
            "or pass serving_model_id in the request body."
        )
        self.project_id = project_id
