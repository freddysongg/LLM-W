from __future__ import annotations

from typing import Any

from app.schemas.model import LayerNode, ModelArchitectureResponse, ResourceEstimate

# Bytes per parameter by dtype
_DTYPE_BYTES: dict[str, float] = {
    "float32": 4.0,
    "float16": 2.0,
    "bfloat16": 2.0,
    "int8": 1.0,
    "int4": 0.5,
    "auto": 2.0,
}

# Training overhead factor: activations + gradients + optimizer states
_TRAINING_MEMORY_MULTIPLIER = 4.0


def estimate_resource_usage(*, total_parameters: int, torch_dtype: str) -> ResourceEstimate:
    bytes_per_param = _DTYPE_BYTES.get(torch_dtype, 2.0)
    vram_gb = (total_parameters * bytes_per_param) / (1024**3)
    # Disk usage: safetensors stores at the same precision
    disk_gb = vram_gb
    training_memory_gb = vram_gb * _TRAINING_MEMORY_MULTIPLIER
    return ResourceEstimate(
        vram_gb=round(vram_gb, 3),
        disk_gb=round(disk_gb, 3),
        training_memory_gb=round(training_memory_gb, 3),
    )


def _build_node(*, name: str, module: Any, depth: int) -> LayerNode:
    """Recursively build a LayerNode from a torch.nn.Module."""
    children_list = list(module.named_children())
    module_type = type(module).__name__

    # Leaf node: no children
    if not children_list:
        params = sum(p.numel() for p in module.parameters(recurse=False))
        is_trainable = any(p.requires_grad for p in module.parameters(recurse=False))
        weight = getattr(module, "weight", None)
        dtype = str(weight.dtype) if weight is not None else None
        shape = list(weight.shape) if weight is not None else None
        return LayerNode(
            name=name,
            type=module_type,
            params=params,
            trainable=is_trainable,
            dtype=dtype,
            shape=shape,
            children=None,
        )

    # Intermediate node: recurse into children
    children: list[LayerNode] = [
        _build_node(name=child_name, module=child_module, depth=depth + 1)
        for child_name, child_module in children_list
    ]
    params = sum(p.numel() for p in module.parameters(recurse=False))
    is_trainable = any(p.requires_grad for p in module.parameters(recurse=False))
    return LayerNode(
        name=name,
        type=module_type,
        params=params if params > 0 else None,
        trainable=is_trainable if params > 0 else None,
        dtype=None,
        shape=None,
        children=children,
    )


def build_architecture_response(
    *,
    model: Any,
    model_id: str,
) -> ModelArchitectureResponse:
    """Build a full architecture response from a loaded torch.nn.Module."""
    total_parameters = sum(p.numel() for p in model.parameters())
    trainable_parameters = sum(p.numel() for p in model.parameters() if p.requires_grad)
    architecture_name = type(model).__name__

    tree = _build_node(name=architecture_name, module=model, depth=0)
    return ModelArchitectureResponse(
        model_id=model_id,
        architecture_name=architecture_name,
        total_parameters=total_parameters,
        trainable_parameters=trainable_parameters,
        tree=tree,
    )


def count_parameters_from_config(hf_config: Any) -> tuple[int, int]:
    """
    Estimate total parameters by instantiating the model on a meta device.
    Returns (total_parameters, trainable_parameters).
    """
    try:
        import torch
        from transformers import AutoModelForCausalLM
    except ImportError as exc:
        raise RuntimeError("torch and transformers are required for parameter counting.") from exc

    with torch.device("meta"):
        meta_model = AutoModelForCausalLM.from_config(hf_config)
    total = sum(p.numel() for p in meta_model.parameters())
    trainable = sum(p.numel() for p in meta_model.parameters() if p.requires_grad)
    return total, trainable
