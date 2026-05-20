from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LlmProvider = Literal["openai", "anthropic"]


@dataclass(frozen=True)
class LlmModelOption:
    provider: LlmProvider
    model_id: str
    label: str


LLM_MODEL_CATALOG: tuple[LlmModelOption, ...] = (
    LlmModelOption(provider="openai", model_id="gpt-4o", label="gpt-4o"),
    LlmModelOption(provider="openai", model_id="gpt-4o-mini", label="gpt-4o-mini"),
    LlmModelOption(provider="openai", model_id="gpt-4-turbo", label="gpt-4-turbo"),
    LlmModelOption(provider="openai", model_id="gpt-3.5-turbo", label="gpt-3.5-turbo"),
    LlmModelOption(provider="openai", model_id="o1", label="o1"),
    LlmModelOption(provider="openai", model_id="o1-mini", label="o1-mini"),
    LlmModelOption(provider="openai", model_id="o3-mini", label="o3-mini"),
    LlmModelOption(
        provider="anthropic", model_id="claude-opus-4-6", label="claude-opus-4-6"
    ),
    LlmModelOption(
        provider="anthropic", model_id="claude-sonnet-4-6", label="claude-sonnet-4-6"
    ),
    LlmModelOption(
        provider="anthropic",
        model_id="claude-sonnet-4-5-20250514",
        label="claude-sonnet-4-5-20250514",
    ),
    LlmModelOption(
        provider="anthropic",
        model_id="claude-haiku-4-5-20251001",
        label="claude-haiku-4-5-20251001",
    ),
)
