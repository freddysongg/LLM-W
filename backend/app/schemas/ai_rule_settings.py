from __future__ import annotations

from pydantic import BaseModel, Field

RULE_NAMES: tuple[str, ...] = (
    "loss_plateau",
    "loss_spike",
    "grad_norm_exploding",
    "eval_diverging",
    "very_low_loss",
    "high_truncation",
    "memory_limit",
)


class AIRuleConfig(BaseModel):
    enabled: bool = True


class AIRuleSettings(BaseModel):
    loss_plateau: AIRuleConfig = Field(default_factory=AIRuleConfig)
    loss_spike: AIRuleConfig = Field(default_factory=AIRuleConfig)
    grad_norm_exploding: AIRuleConfig = Field(default_factory=AIRuleConfig)
    eval_diverging: AIRuleConfig = Field(default_factory=AIRuleConfig)
    very_low_loss: AIRuleConfig = Field(default_factory=AIRuleConfig)
    high_truncation: AIRuleConfig = Field(default_factory=AIRuleConfig)
    memory_limit: AIRuleConfig = Field(default_factory=AIRuleConfig)


class AIRuleSettingsResponse(AIRuleSettings):
    pass


class AIRuleSettingsUpdateRequest(AIRuleSettings):
    pass
