from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

import yaml

from app.services.rule_engine import AISuggestionCreate, evaluate_rules


class RecommendationEngine(ABC):
    """Interface for recommendation engines. Implementations: RuleBasedEngine, CloudLLMEngine."""

    @abstractmethod
    async def generate_recommendations(
        self,
        *,
        config: dict[str, Any],
        run_metrics: list[dict[str, Any]],
        dataset_profile: dict[str, Any],
        comparison_data: dict[str, Any] | None,
        notes: str | None,
    ) -> list[AISuggestionCreate]: ...

    @abstractmethod
    async def health_check(self) -> bool: ...


class RuleBasedEngine(RecommendationEngine):
    async def generate_recommendations(
        self,
        *,
        config: dict[str, Any],
        run_metrics: list[dict[str, Any]],
        dataset_profile: dict[str, Any],
        comparison_data: dict[str, Any] | None,
        notes: str | None,
    ) -> list[AISuggestionCreate]:
        return evaluate_rules(metrics=run_metrics, config=config)

    async def health_check(self) -> bool:
        return True


def _build_prompt(
    *,
    config_yaml: str,
    run_metrics: list[dict[str, Any]],
    dataset_profile: dict[str, Any],
    comparison_data: dict[str, Any] | None,
    notes: str | None,
) -> str:
    sections: list[str] = [
        "You are an expert ML training advisor for LLM fine-tuning.",
        "Analyse the training run evidence below and return a JSON suggestion.",
        "",
        "## Current Configuration (YAML)",
        "```yaml",
        config_yaml.strip(),
        "```",
    ]

    if run_metrics:
        # Summarise metrics to avoid huge payloads
        metric_summary: dict[str, list[float]] = {}
        for point in run_metrics:
            name = str(point.get("metric_name", ""))
            value = float(point.get("value", 0.0))
            metric_summary.setdefault(name, []).append(value)

        summary_lines = []
        for name, values in sorted(metric_summary.items()):
            first, last = values[0], values[-1]
            summary_lines.append(f"  {name}: first={first:.4f}, last={last:.4f}, n={len(values)}")

        sections += ["", "## Run Metrics Summary", *summary_lines]

    if dataset_profile:
        sections += [
            "",
            "## Dataset Profile",
            json.dumps(dataset_profile, indent=2),
        ]

    if comparison_data:
        sections += [
            "",
            "## Comparison Data",
            json.dumps(comparison_data, indent=2),
        ]

    if notes:
        sections += ["", "## User Notes", notes]

    sections += [
        "",
        "## Instructions",
        "Return ONLY valid JSON with this exact schema (no markdown, no extra text):",
        json.dumps(
            {
                "config_diff": {
                    "training.learning_rate": {"current": 0.0002, "suggested": 0.0001}
                },
                "rationale": "string",
                "evidence": [
                    {
                        "type": "metric",
                        "reference_id": "string",
                        "label": "string",
                        "value": "string",
                    }
                ],
                "expected_effect": "string",
                "tradeoffs": "string",
                "confidence": 0.75,
                "risk_level": "low",
            },
            indent=2,
        ),
        "",
        "config_diff keys must be dot-notation paths (e.g. 'training.learning_rate').",
        "risk_level must be one of: low, medium, high.",
        "confidence must be a float between 0 and 1.",
    ]

    return "\n".join(sections)


def _parse_llm_response(*, raw: str, provider: str) -> AISuggestionCreate:
    try:
        data = json.loads(raw.strip())
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("LLM response is not a JSON object")

    config_diff = data.get("config_diff") or {}
    if not isinstance(config_diff, dict):
        config_diff = {}

    evidence_raw = data.get("evidence") or []
    evidence: list[dict[str, Any]] = [e for e in evidence_raw if isinstance(e, dict)]

    risk_level = data.get("risk_level")
    if risk_level not in ("low", "medium", "high", None):
        risk_level = None

    confidence = data.get("confidence")
    if confidence is not None:
        try:
            confidence = float(confidence)
            confidence = max(0.0, min(1.0, confidence))
        except (TypeError, ValueError):
            confidence = None

    return AISuggestionCreate(
        config_diff=config_diff,
        rationale=str(data.get("rationale") or ""),
        evidence=evidence,
        provider=provider,
        expected_effect=str(data["expected_effect"]) if data.get("expected_effect") else None,
        tradeoffs=str(data["tradeoffs"]) if data.get("tradeoffs") else None,
        confidence=confidence,
        risk_level=risk_level,
    )


class CloudLLMEngine(RecommendationEngine):
    def __init__(self, *, provider: str, api_key: str, model_id: str, base_url: str | None) -> None:
        self._provider = provider
        self._api_key = api_key
        self._model_id = model_id
        # Resolve base_url: 'openai' always uses the canonical endpoint regardless of
        # what the caller passes (base_url is cleared when switching providers).
        # 'openai_compatible' uses the caller-supplied URL.
        # 'anthropic' ignores base_url entirely (_call_anthropic does not use it).
        self._base_url: str | None = (
            "https://api.openai.com/v1" if provider == "openai" else base_url
        )

    async def generate_recommendations(
        self,
        *,
        config: dict[str, Any],
        run_metrics: list[dict[str, Any]],
        dataset_profile: dict[str, Any],
        comparison_data: dict[str, Any] | None,
        notes: str | None,
    ) -> list[AISuggestionCreate]:
        config_yaml = yaml.dump(config, default_flow_style=False, allow_unicode=True)
        prompt = _build_prompt(
            config_yaml=config_yaml,
            run_metrics=run_metrics,
            dataset_profile=dataset_profile,
            comparison_data=comparison_data,
            notes=notes,
        )
        raw = await self._call_api(prompt=prompt)
        suggestion = _parse_llm_response(raw=raw, provider=self._provider)
        return [suggestion]

    async def _call_api(self, *, prompt: str) -> str:
        if self._provider == "anthropic":
            return await self._call_anthropic(prompt=prompt)
        if self._provider in ("openai", "openai_compatible"):
            return await self._call_openai(prompt=prompt)
        raise ValueError(f"Unsupported provider: {self._provider}")

    async def _call_anthropic(self, *, prompt: str) -> str:
        import asyncio

        import anthropic

        client = anthropic.Anthropic(api_key=self._api_key)
        # Anthropic SDK is synchronous — run in threadpool for async compatibility

        def _sync_call() -> str:
            try:
                response = client.messages.create(
                    model=self._model_id,
                    max_tokens=2048,
                    messages=[{"role": "user", "content": prompt}],
                )
            except anthropic.AuthenticationError as exc:
                raise ValueError(f"Anthropic authentication failed: {exc}") from exc
            except anthropic.APIConnectionError as exc:
                raise ValueError(f"Anthropic connection error: {exc}") from exc
            except anthropic.APIStatusError as exc:
                raise ValueError(f"Anthropic API error {exc.status_code}: {exc.message}") from exc
            block = response.content[0]
            if hasattr(block, "text"):
                return block.text  # type: ignore[no-any-return]
            raise ValueError("Unexpected Anthropic response content type")

        return await asyncio.get_running_loop().run_in_executor(None, _sync_call)

    async def _call_openai(self, *, prompt: str) -> str:
        import asyncio

        import openai

        client = openai.OpenAI(api_key=self._api_key, base_url=self._base_url)

        def _sync_call() -> str:
            try:
                response = client.chat.completions.create(
                    model=self._model_id,
                    max_tokens=2048,
                    messages=[{"role": "user", "content": prompt}],
                )
            except openai.AuthenticationError as exc:
                raise ValueError(f"OpenAI authentication failed: {exc}") from exc
            except openai.APIConnectionError as exc:
                raise ValueError(f"OpenAI connection error: {exc}") from exc
            except openai.APIStatusError as exc:
                raise ValueError(f"OpenAI API error {exc.status_code}: {exc.message}") from exc
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("OpenAI returned empty content")
            return content

        return await asyncio.get_running_loop().run_in_executor(None, _sync_call)

    async def health_check(self) -> bool:
        try:
            if self._provider == "anthropic":
                import anthropic

                client = anthropic.Anthropic(api_key=self._api_key)
                client.messages.create(
                    model=self._model_id,
                    max_tokens=1,
                    messages=[{"role": "user", "content": "ping"}],
                )
            elif self._provider in ("openai", "openai_compatible"):
                import openai

                client = openai.OpenAI(api_key=self._api_key, base_url=self._base_url)
                client.chat.completions.create(
                    model=self._model_id,
                    max_tokens=1,
                    messages=[{"role": "user", "content": "ping"}],
                )
            else:
                return False
        except Exception:
            return False
        return True


def build_engine(
    *,
    provider: str,
    api_key: str | None,
    model_id: str,
    base_url: str | None,
) -> RecommendationEngine:
    """Return the best available engine given the current settings."""
    if api_key and provider in ("anthropic", "openai", "openai_compatible"):
        return CloudLLMEngine(
            provider=provider,
            api_key=api_key,
            model_id=model_id,
            base_url=base_url,
        )
    return RuleBasedEngine()
