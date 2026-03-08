from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.adapters.base import ModelAdapter

if TYPE_CHECKING:
    from app.schemas.workbench_config import AdaptersConfig, ModelConfig


class CausalLMAdapter(ModelAdapter):
    """
    ModelAdapter implementation for causal decoder-only language models.
    Wraps HuggingFace AutoModelForCausalLM and AutoTokenizer.
    """

    def __init__(self) -> None:
        self._model: Any = None
        self._tokenizer: Any = None
        self._config: ModelConfig | None = None

    def load_model(self, config: ModelConfig) -> None:
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "transformers is required for model loading. "
                "Install with: pip install transformers"
            ) from exc

        self._config = config
        self._tokenizer = AutoTokenizer.from_pretrained(
            config.model_id,
            revision=config.revision,
            trust_remote_code=config.trust_remote_code,
        )
        self._model = AutoModelForCausalLM.from_pretrained(
            config.model_id,
            revision=config.revision,
            trust_remote_code=config.trust_remote_code,
        )

    def get_architecture_family(self) -> str:
        return "causal_lm"

    def get_task_compatibility(self) -> list[str]:
        return ["text-generation", "causal-language-modeling", "sft"]

    def get_tokenizer_info(self) -> dict[str, Any]:
        if self._tokenizer is None:
            return {}
        return {
            "vocab_size": self._tokenizer.vocab_size,
            "model_max_length": getattr(self._tokenizer, "model_max_length", None),
            "padding_side": self._tokenizer.padding_side,
            "bos_token": self._tokenizer.bos_token,
            "eos_token": self._tokenizer.eos_token,
            "pad_token": self._tokenizer.pad_token,
        }

    def get_supported_training_modes(self) -> list[str]:
        return ["sft"]

    def get_supported_adapter_methods(self) -> list[str]:
        return ["lora", "qlora"]

    def get_quantization_support(self) -> list[str]:
        return ["int8", "int4", "fp16", "bf16", "float32"]

    def get_introspection_support(self) -> dict[str, bool]:
        return {
            "architecture_tree": True,
            "layer_inspection": True,
            "activation_capture": True,
            "gradient_capture": True,
            "delta_analysis": True,
        }

    def discover_trainable_modules(self) -> list[str]:
        if self._model is None:
            # Return common LoRA targets for decoder-only models as a default
            return ["q_proj", "v_proj", "k_proj", "o_proj"]
        seen: set[str] = set()
        candidates: list[str] = []
        for name, module in self._model.named_modules():
            if type(module).__name__ == "Linear":
                leaf = name.split(".")[-1]
                if leaf not in seen:
                    seen.add(leaf)
                    candidates.append(leaf)
        return candidates

    def get_checkpoint_compatibility(self) -> dict[str, Any]:
        return {
            "format": "safetensors",
            "supports_lora_merge": True,
            "supports_full_merge": True,
        }

    def inspect_layers(self) -> list[dict[str, Any]]:
        if self._model is None:
            return []
        layers: list[dict[str, Any]] = []
        for name, module in self._model.named_modules():
            params = sum(p.numel() for p in module.parameters(recurse=False))
            is_trainable = any(
                p.requires_grad for p in module.parameters(recurse=False)
            )
            weight = getattr(module, "weight", None)
            dtype = str(weight.dtype) if weight is not None else None
            shape = list(weight.shape) if weight is not None else None
            layers.append(
                {
                    "name": name,
                    "type": type(module).__name__,
                    "params": params,
                    "trainable": is_trainable,
                    "dtype": dtype,
                    "shape": shape,
                }
            )
        return layers

    def attach_adapters(self, adapter_config: AdaptersConfig) -> None:
        try:
            from peft import LoraConfig, TaskType, get_peft_model
        except ImportError as exc:
            raise RuntimeError(
                "peft is required for adapter attachment. Install with: pip install peft"
            ) from exc
        if self._model is None:
            raise RuntimeError("Model must be loaded before attaching adapters.")
        lora_config = LoraConfig(
            r=adapter_config.rank,
            lora_alpha=adapter_config.alpha,
            lora_dropout=adapter_config.dropout,
            target_modules=adapter_config.target_modules,
            task_type=TaskType.CAUSAL_LM,
        )
        self._model = get_peft_model(self._model, lora_config)

    def run_train_step(self, batch: Any) -> dict[str, float]:
        raise NotImplementedError("Training steps are managed by the trainer worker.")

    def run_eval_step(self, batch: Any) -> dict[str, float]:
        raise NotImplementedError("Eval steps are managed by the trainer worker.")

    def capture_activations(
        self, *, layer_names: list[str], sample_input: Any
    ) -> dict[str, Any]:
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError(
                "torch is required for activation capture. Install with: pip install torch"
            ) from exc
        if self._model is None or self._tokenizer is None:
            raise RuntimeError("Model must be loaded before capturing activations.")

        captured: dict[str, Any] = {}
        hooks: list[Any] = []

        def _make_hook(layer_name: str) -> Any:
            def _hook(module: Any, _input: Any, output: Any) -> None:
                tensor = output[0] if isinstance(output, tuple) else output
                tensor_f = tensor.float().cpu()
                hist_result = torch.histogram(tensor_f.flatten(), bins=10)
                captured[layer_name] = {
                    "mean": float(tensor_f.mean()),
                    "std": float(tensor_f.std()),
                    "min": float(tensor_f.min()),
                    "max": float(tensor_f.max()),
                    "shape": list(tensor.shape),
                    "histogram_bins": [float(v) for v in hist_result.hist],
                }

            return _hook

        module_map = dict(self._model.named_modules())
        for layer_name in layer_names:
            if layer_name in module_map:
                hooks.append(
                    module_map[layer_name].register_forward_hook(_make_hook(layer_name))
                )

        inputs = self._tokenizer(
            sample_input, return_tensors="pt", truncation=True, max_length=512
        )
        with torch.no_grad():
            self._model(**inputs)

        for hook in hooks:
            hook.remove()

        return captured

    def capture_deltas(
        self, *, checkpoint_before: str, checkpoint_after: str
    ) -> dict[str, Any]:
        # Delta analysis between checkpoints is implemented in the training phase
        raise NotImplementedError(
            f"Delta capture between {checkpoint_before} and {checkpoint_after} "
            "is not implemented in this phase."
        )

    def export_checkpoint(self, *, output_path: str) -> str:
        if self._model is None:
            raise RuntimeError("Model must be loaded before exporting.")
        self._model.save_pretrained(output_path)
        if self._tokenizer is not None:
            self._tokenizer.save_pretrained(output_path)
        return output_path
