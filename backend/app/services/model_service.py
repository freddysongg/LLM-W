from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from app.adapters.causal_lm import CausalLMAdapter
from app.core.exceptions import (
    ActivationSnapshotNotFoundError,
    LayerNotFoundError,
    ModelNotResolvedError,
    ModelResolveError,
)
from app.schemas.model import (
    ActivationCaptureRequest,
    ActivationLayerSnapshot,
    ActivationSnapshotResponse,
    DeltaComputeRequest,
    FullTensorRequest,
    FullTensorResponse,
    LayerDetailResponse,
    ModelArchitectureResponse,
    ModelProfile,
    ModelResolveRequest,
    TierOneStats,
    WeightDeltaResponse,
)
from app.services.introspection import (
    build_architecture_from_config,
    build_architecture_response,
    compute_weight_deltas,
    count_parameters_from_config,
    estimate_resource_usage,
)

# In-memory state keyed by project_id
_profiles: dict[str, ModelProfile] = {}
_adapters: dict[str, CausalLMAdapter] = {}
_activation_snapshots: dict[str, ActivationSnapshotResponse] = {}
_architecture_cache: dict[str, ModelArchitectureResponse] = {}


def _resolve_model_sync(*, project_id: str, request: ModelResolveRequest) -> ModelProfile:
    try:
        from transformers import AutoConfig
    except ImportError as exc:
        raise ModelResolveError(
            "transformers is not installed. Install the training extras: "
            "pip install 'llm-workbench-backend[training]'"
        ) from exc

    try:
        hf_config = AutoConfig.from_pretrained(
            request.model_id,
            revision=request.revision,
            trust_remote_code=request.trust_remote_code,
        )
    except Exception as exc:
        raise ModelResolveError(
            f"Failed to load model config for '{request.model_id}': {exc}"
        ) from exc

    try:
        total_parameters, trainable_parameters = count_parameters_from_config(hf_config)
    except Exception:
        # If meta-device instantiation fails, fall back to zero counts
        total_parameters = 0
        trainable_parameters = 0

    try:
        _architecture_cache[project_id] = build_architecture_from_config(
            hf_config=hf_config,
            model_id=request.model_id,
        )
    except Exception:
        # Non-fatal: architecture will be built lazily from the loaded model on first request
        pass

    architecture_name = type(hf_config).__name__.replace("Config", "ForCausalLM")
    torch_dtype = getattr(hf_config, "torch_dtype", None)
    if torch_dtype is None:
        torch_dtype = "auto"
    elif not isinstance(torch_dtype, str):
        torch_dtype = str(torch_dtype).split(".")[-1]

    vocabulary_size: int | None = getattr(hf_config, "vocab_size", None)
    context_length: int | None = (
        getattr(hf_config, "max_position_embeddings", None)
        or getattr(hf_config, "n_positions", None)
        or getattr(hf_config, "seq_length", None)
    )

    resource_estimate = estimate_resource_usage(
        total_parameters=total_parameters,
        torch_dtype=request.model_id and torch_dtype or "auto",
    )

    adapter = CausalLMAdapter()
    _adapters[project_id] = adapter

    return ModelProfile(
        model_id=request.model_id,
        source=request.source,
        family="causal_lm",
        architecture_name=architecture_name,
        total_parameters=total_parameters,
        trainable_parameters=trainable_parameters,
        resource_estimate=resource_estimate,
        torch_dtype=torch_dtype,
        vocabulary_size=vocabulary_size,
        context_length=context_length,
        resolved_at=datetime.now(UTC).isoformat(),
    )


async def resolve_model(*, project_id: str, request: ModelResolveRequest) -> ModelProfile:
    # Clear stale architecture cache so re-resolving a different model updates the response
    _architecture_cache.pop(project_id, None)
    loop = asyncio.get_event_loop()
    profile = await loop.run_in_executor(
        None,
        lambda: _resolve_model_sync(project_id=project_id, request=request),
    )
    _profiles[project_id] = profile
    return profile


def get_model_profile(*, project_id: str) -> ModelProfile:
    profile = _profiles.get(project_id)
    if profile is None:
        raise ModelNotResolvedError(project_id)
    return profile


def _get_loaded_adapter(*, project_id: str) -> CausalLMAdapter:
    """Return the adapter for a project, loading the full model if needed."""
    profile = _profiles.get(project_id)
    if profile is None:
        raise ModelNotResolvedError(project_id)

    adapter = _adapters.get(project_id)
    if adapter is None:
        raise ModelNotResolvedError(project_id)

    if adapter._model is None:
        try:
            from app.schemas.workbench_config import ModelConfig
        except ImportError as exc:
            raise ModelResolveError("Internal error: could not import ModelConfig") from exc
        model_config = ModelConfig(
            source=profile.source,
            model_id=profile.model_id,
        )
        adapter.load_model(model_config)

    return adapter


def _get_architecture_sync(*, project_id: str) -> ModelArchitectureResponse:
    cached = _architecture_cache.get(project_id)
    if cached is not None:
        return cached

    # Fallback: load the full model and build from it (slower path for post-restart requests)
    adapter = _get_loaded_adapter(project_id=project_id)
    profile = _profiles[project_id]
    result = build_architecture_response(model=adapter._model, model_id=profile.model_id)
    _architecture_cache[project_id] = result
    return result


async def get_model_architecture(*, project_id: str) -> ModelArchitectureResponse:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: _get_architecture_sync(project_id=project_id),
    )


def get_layer_detail(*, project_id: str, layer_name: str) -> LayerDetailResponse:
    adapter = _adapters.get(project_id)
    if adapter is None or adapter._model is None:
        raise ModelNotResolvedError(project_id)

    module_map = dict(adapter._model.named_modules())
    if layer_name not in module_map:
        raise LayerNotFoundError(layer_name)

    module = module_map[layer_name]
    params = sum(p.numel() for p in module.parameters(recurse=False))
    is_trainable = any(p.requires_grad for p in module.parameters(recurse=False))
    weight = getattr(module, "weight", None)
    dtype = str(weight.dtype) if weight is not None else None
    shape = list(weight.shape) if weight is not None else None

    return LayerDetailResponse(
        name=layer_name,
        type=type(module).__name__,
        params=params,
        trainable=is_trainable,
        dtype=dtype,
        shape=shape,
    )


def _capture_activations_sync(
    *, project_id: str, request: ActivationCaptureRequest
) -> ActivationSnapshotResponse:
    adapter = _get_loaded_adapter(project_id=project_id)
    raw = adapter.capture_activations(
        layer_names=request.layer_names,
        sample_input=request.sample_input,
    )

    layer_snapshots: list[ActivationLayerSnapshot] = []
    for layer_name, stats in raw.items():
        tier1 = TierOneStats(
            mean=stats["mean"],
            std=stats["std"],
            min=stats["min"],
            max=stats["max"],
            histogram_bins=stats["histogram_bins"],
        )
        layer_snapshots.append(
            ActivationLayerSnapshot(
                layer_name=layer_name,
                tier1=tier1,
                shape=stats["shape"],
            )
        )

    snapshot = ActivationSnapshotResponse(
        id=str(uuid.uuid4()),
        created_at=datetime.now(UTC).isoformat(),
        layers=layer_snapshots,
    )
    _activation_snapshots[snapshot.id] = snapshot
    return snapshot


async def capture_activations(
    *, project_id: str, request: ActivationCaptureRequest
) -> ActivationSnapshotResponse:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: _capture_activations_sync(project_id=project_id, request=request),
    )


def get_activation_snapshot(*, project_id: str, snapshot_id: str) -> ActivationSnapshotResponse:
    snapshot = _activation_snapshots.get(snapshot_id)
    if snapshot is None:
        raise ActivationSnapshotNotFoundError(snapshot_id)
    return snapshot


async def compute_model_deltas(
    *, project_id: str, request: DeltaComputeRequest
) -> WeightDeltaResponse:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: compute_weight_deltas(
            checkpoint_before=request.checkpoint_before,
            checkpoint_after=request.checkpoint_after,
        ),
    )


def get_full_tensor(
    *, project_id: str, snapshot_id: str, request: FullTensorRequest
) -> FullTensorResponse:
    """
    Full tensor capture is a Tier 2 operation (on-demand).
    Returns raw tensor data for requested layers from the snapshot.
    """
    snapshot = _activation_snapshots.get(snapshot_id)
    if snapshot is None:
        raise ActivationSnapshotNotFoundError(snapshot_id)

    requested_names: set[str] = (
        set(request.layer_names) if request.layer_names else {s.layer_name for s in snapshot.layers}
    )

    layer_tensors: dict[str, Any] = {
        layer.layer_name: {
            "tier1": layer.tier1.model_dump(),
            "shape": layer.shape,
        }
        for layer in snapshot.layers
        if layer.layer_name in requested_names
    }

    return FullTensorResponse(snapshot_id=snapshot_id, layer_tensors=layer_tensors)
