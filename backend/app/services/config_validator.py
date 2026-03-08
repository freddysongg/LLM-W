from __future__ import annotations

from dataclasses import dataclass, field

import yaml
from pydantic import ValidationError

from app.schemas.workbench_config import WorkbenchConfig


@dataclass
class ConfigValidationResult:
    is_valid: bool
    config: WorkbenchConfig | None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_workbench_config(*, yaml_content: str) -> ConfigValidationResult:
    try:
        parsed = yaml.safe_load(yaml_content)
    except yaml.YAMLError as exc:
        return ConfigValidationResult(
            is_valid=False,
            config=None,
            errors=[f"YAML parse error: {exc}"],
        )

    if not isinstance(parsed, dict):
        return ConfigValidationResult(
            is_valid=False,
            config=None,
            errors=["Config must be a YAML mapping"],
        )

    try:
        config = WorkbenchConfig.model_validate(parsed)
    except ValidationError as exc:
        errors = [
            f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}"
            for e in exc.errors()
        ]
        return ConfigValidationResult(is_valid=False, config=None, errors=errors)

    warnings: list[str] = []
    if not config.model.model_id:
        warnings.append("model.model_id is empty — model must be configured before running")
    if not config.dataset.dataset_id:
        warnings.append("dataset.dataset_id is empty — dataset must be configured before running")

    return ConfigValidationResult(is_valid=True, config=config, warnings=warnings)
