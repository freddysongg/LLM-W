from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.schemas.workbench_config import AdaptersConfig, ModelConfig


class ModelAdapter(ABC):
    """
    Abstract interface for model integrations.
    Each model family implements this contract.
    """

    @abstractmethod
    def load_model(self, config: ModelConfig) -> None: ...

    @abstractmethod
    def get_architecture_family(self) -> str: ...

    @abstractmethod
    def get_task_compatibility(self) -> list[str]: ...

    @abstractmethod
    def get_tokenizer_info(self) -> dict[str, Any]: ...

    @abstractmethod
    def get_supported_training_modes(self) -> list[str]: ...

    @abstractmethod
    def get_supported_adapter_methods(self) -> list[str]: ...

    @abstractmethod
    def get_quantization_support(self) -> list[str]: ...

    @abstractmethod
    def get_introspection_support(self) -> dict[str, bool]: ...

    @abstractmethod
    def discover_trainable_modules(self) -> list[str]: ...

    @abstractmethod
    def get_checkpoint_compatibility(self) -> dict[str, Any]: ...

    @abstractmethod
    def inspect_layers(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def attach_adapters(self, adapter_config: AdaptersConfig) -> None: ...

    @abstractmethod
    def run_train_step(self, batch: Any) -> dict[str, float]: ...

    @abstractmethod
    def run_eval_step(self, batch: Any) -> dict[str, float]: ...

    @abstractmethod
    def capture_activations(
        self, *, layer_names: list[str], sample_input: Any
    ) -> dict[str, Any]: ...

    @abstractmethod
    def capture_deltas(
        self, *, checkpoint_before: str, checkpoint_after: str
    ) -> dict[str, Any]: ...

    @abstractmethod
    def export_checkpoint(self, *, output_path: str) -> str: ...
