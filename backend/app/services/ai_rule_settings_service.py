"""Per-project enable/disable toggles for the rule-engine suggestions.

Rule settings are operator preferences about which rule-engine signals should
surface — they are not training behavior, so they do not belong in the
versioned project config. The file lives at
``{project.directory_path}/ai_rule_settings.yaml`` and is read on every
suggestion generation so toggling a rule takes effect on the next Re-scan
without requiring a new config version.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from app.schemas.ai_rule_settings import (
    RULE_NAMES,
    AIRuleConfig,
    AIRuleSettings,
)

_SETTINGS_FILENAME = "ai_rule_settings.yaml"


def _settings_path(*, project_dir: Path) -> Path:
    return project_dir / _SETTINGS_FILENAME


def _default_settings() -> AIRuleSettings:
    return AIRuleSettings(
        **{rule_name: AIRuleConfig(enabled=True) for rule_name in RULE_NAMES}
    )


def get_rule_settings(*, project_dir: Path) -> AIRuleSettings:
    """Return the project's per-rule toggles, defaulting to all-enabled.

    A missing file means the project has never been configured; defaults match
    the historic behavior where every rule was always evaluated.
    """
    path = _settings_path(project_dir=project_dir)
    if not path.exists():
        return _default_settings()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return _default_settings()
    return AIRuleSettings.model_validate(raw)


def save_rule_settings(
    *, project_dir: Path, settings: AIRuleSettings
) -> AIRuleSettings:
    """Persist toggles atomically and return the saved record."""
    path = _settings_path(project_dir=project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = settings.model_dump()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    os.replace(tmp, path)
    return settings


def disabled_rule_names(settings: AIRuleSettings) -> set[str]:
    """Helper for the rule engine — names of rules that are toggled off."""
    return {
        name for name in RULE_NAMES if not getattr(settings, name).enabled
    }
