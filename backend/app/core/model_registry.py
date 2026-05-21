from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRegistryEntry:
    name: str
    params: str
    context: str
    license: str
    source: str
    is_pinned: bool


MODEL_REGISTRY: tuple[ModelRegistryEntry, ...] = (
    ModelRegistryEntry(
        name="qwen2.5-1.5b",
        params="1.54B",
        context="32k",
        license="Apache-2.0",
        source="HF",
        is_pinned=True,
    ),
    ModelRegistryEntry(
        name="qwen2.5-7b",
        params="7.61B",
        context="32k",
        license="Apache-2.0",
        source="HF",
        is_pinned=False,
    ),
    ModelRegistryEntry(
        name="mistral-7b-v0.3",
        params="7.25B",
        context="32k",
        license="Apache-2.0",
        source="HF",
        is_pinned=False,
    ),
    ModelRegistryEntry(
        name="llama-3-8b",
        params="8.03B",
        context="8k",
        license="Meta-Community",
        source="HF",
        is_pinned=False,
    ),
    ModelRegistryEntry(
        name="tinyllama-1.1b",
        params="1.10B",
        context="2k",
        license="Apache-2.0",
        source="HF",
        is_pinned=False,
    ),
    ModelRegistryEntry(
        name="phi-3-mini-4k",
        params="3.82B",
        context="4k",
        license="MIT",
        source="HF",
        is_pinned=False,
    ),
    ModelRegistryEntry(
        name="gemma-2b",
        params="2.51B",
        context="8k",
        license="Gemma",
        source="HF",
        is_pinned=False,
    ),
)
