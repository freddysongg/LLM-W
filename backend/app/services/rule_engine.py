from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AISuggestionCreate:
    config_diff: dict[str, dict[str, Any]]
    rationale: str
    evidence: list[dict[str, Any]]
    provider: str
    expected_effect: str | None = None
    tradeoffs: str | None = None
    confidence: float | None = None
    risk_level: str | None = None


def _group_by_metric(
    metrics: list[dict[str, Any]],
) -> dict[str, list[tuple[int, float]]]:
    """Group metric points by name, returning sorted (step, value) pairs."""
    grouped: dict[str, list[tuple[int, float]]] = {}
    for point in metrics:
        name = point.get("metric_name", "")
        step = int(point.get("step", 0))
        value = float(point.get("value", 0.0))
        grouped.setdefault(name, []).append((step, value))
    for series in grouped.values():
        series.sort(key=lambda t: t[0])
    return grouped


def _check_loss_plateau(
    grouped: dict[str, list[tuple[int, float]]],
    current_lr: float,
) -> AISuggestionCreate | None:
    series = grouped.get("eval_loss") or grouped.get("loss")
    if not series or len(series) < 5:
        return None

    recent = series[-5:]
    first_val = recent[0][1]
    if first_val == 0.0:
        return None

    max_change = max(abs(v - first_val) / first_val for _, v in recent[1:])
    if max_change >= 0.01:
        return None

    suggested_lr = round(current_lr * 0.5, 8)
    return AISuggestionCreate(
        config_diff={
            "training.learning_rate": {"current": current_lr, "suggested": suggested_lr},
        },
        rationale=(
            "Loss has changed less than 1% over the last 5 evaluation steps, "
            "indicating a plateau. Reducing the learning rate may help the model "
            "escape the plateau and continue improving."
        ),
        evidence=[
            {
                "type": "metric",
                "reference_id": "eval_loss",
                "label": "Loss change over last 5 steps",
                "value": f"{max_change * 100:.3f}%",
            }
        ],
        provider="rule_engine",
        expected_effect="Smaller gradient updates allow finer convergence past the plateau.",
        tradeoffs="Training may take longer to converge with a lower learning rate.",
        confidence=0.7,
        risk_level="low",
    )


def _check_loss_spike(
    grouped: dict[str, list[tuple[int, float]]],
    current_lr: float,
    current_warmup_ratio: float,
) -> AISuggestionCreate | None:
    series = grouped.get("train_loss") or grouped.get("loss")
    if not series or len(series) < 2:
        return None

    spike_step: int | None = None
    spike_pct: float = 0.0
    for i in range(1, len(series)):
        prev_val = series[i - 1][1]
        curr_val = series[i][1]
        if prev_val > 0 and (curr_val - prev_val) / prev_val > 0.20:
            spike_pct = (curr_val - prev_val) / prev_val
            spike_step = series[i][0]
            break

    if spike_step is None:
        return None

    suggested_lr = round(current_lr * 0.7, 8)
    suggested_warmup = round(min(current_warmup_ratio + 0.02, 0.1), 4)
    return AISuggestionCreate(
        config_diff={
            "training.learning_rate": {"current": current_lr, "suggested": suggested_lr},
            "optimization.warmup_ratio": {
                "current": current_warmup_ratio,
                "suggested": suggested_warmup,
            },
        },
        rationale=(
            f"Loss spiked by {spike_pct * 100:.1f}% at step {spike_step}. "
            "This often indicates the learning rate is too aggressive. "
            "Reducing the learning rate and increasing warmup should stabilize training."
        ),
        evidence=[
            {
                "type": "metric",
                "reference_id": "train_loss",
                "label": f"Loss spike at step {spike_step}",
                "value": f"{spike_pct * 100:.1f}%",
            }
        ],
        provider="rule_engine",
        expected_effect="Stabilized loss curve with reduced step-over-step variance.",
        tradeoffs="Lower learning rate may slow overall convergence.",
        confidence=0.75,
        risk_level="low",
    )


def _check_grad_norm_exploding(
    grouped: dict[str, list[tuple[int, float]]],
    current_lr: float,
    current_max_grad_norm: float,
) -> AISuggestionCreate | None:
    series = grouped.get("grad_norm")
    if not series or len(series) < 2:
        return None

    initial_norm = series[0][1]
    if initial_norm == 0.0:
        return None

    latest_norm = series[-1][1]
    ratio = latest_norm / initial_norm
    if ratio < 10.0:
        return None

    suggested_grad_norm = round(current_max_grad_norm * 0.5, 4)
    suggested_lr = round(current_lr * 0.8, 8)
    return AISuggestionCreate(
        config_diff={
            "training.max_grad_norm": {
                "current": current_max_grad_norm,
                "suggested": suggested_grad_norm,
            },
            "training.learning_rate": {"current": current_lr, "suggested": suggested_lr},
        },
        rationale=(
            f"Gradient norm has grown to {ratio:.1f}x the initial value "
            f"({initial_norm:.3f} → {latest_norm:.3f}). "
            "Tighter gradient clipping and a lower learning rate should prevent instability."
        ),
        evidence=[
            {
                "type": "metric",
                "reference_id": "grad_norm",
                "label": "Gradient norm ratio (current / initial)",
                "value": round(ratio, 2),
            }
        ],
        provider="rule_engine",
        expected_effect="Bounded gradient updates prevent instability and NaN losses.",
        tradeoffs="Tighter clipping may slow learning if gradients are legitimately large.",
        confidence=0.8,
        risk_level="medium",
    )


def _check_eval_diverging(
    grouped: dict[str, list[tuple[int, float]]],
    current_epochs: int,
    current_dropout: float,
    current_rank: int,
) -> AISuggestionCreate | None:
    eval_series = grouped.get("eval_loss")
    train_series = grouped.get("train_loss") or grouped.get("loss")
    if not eval_series or not train_series or len(eval_series) < 3:
        return None

    recent_eval = eval_series[-3:]
    eval_increasing = recent_eval[-1][1] > recent_eval[0][1]

    recent_train = train_series[-3:]
    train_decreasing = recent_train[-1][1] < recent_train[0][1]

    if not (eval_increasing and train_decreasing):
        return None

    suggested_epochs = max(1, current_epochs - 1)
    suggested_dropout = round(min(current_dropout + 0.05, 0.3), 3)
    suggested_rank = max(4, current_rank // 2)
    return AISuggestionCreate(
        config_diff={
            "training.epochs": {"current": current_epochs, "suggested": suggested_epochs},
            "adapters.dropout": {"current": current_dropout, "suggested": suggested_dropout},
            "adapters.rank": {"current": current_rank, "suggested": suggested_rank},
        },
        rationale=(
            "Eval loss is increasing while train loss continues to decrease, "
            "a classic sign of overfitting. Reducing epochs, increasing dropout, "
            "and lowering LoRA rank should improve generalization."
        ),
        evidence=[
            {
                "type": "metric",
                "reference_id": "eval_loss",
                "label": "Eval loss trend (last 3 checkpoints)",
                "value": f"{recent_eval[0][1]:.4f} → {recent_eval[-1][1]:.4f}",
            },
            {
                "type": "metric",
                "reference_id": "train_loss",
                "label": "Train loss trend (last 3 steps)",
                "value": f"{recent_train[0][1]:.4f} → {recent_train[-1][1]:.4f}",
            },
        ],
        provider="rule_engine",
        expected_effect="Better generalization on unseen data.",
        tradeoffs=(
            "Lower rank reduces adapter expressiveness. "
            "Fewer epochs may underfit if overfitting is mild."
        ),
        confidence=0.72,
        risk_level="medium",
    )


def _check_very_low_loss(
    grouped: dict[str, list[tuple[int, float]]],
) -> AISuggestionCreate | None:
    series = grouped.get("train_loss") or grouped.get("loss")
    if not series:
        return None

    latest_loss = series[-1][1]
    if latest_loss >= 0.1:
        return None

    return AISuggestionCreate(
        config_diff={},
        rationale=(
            f"Training loss has reached {latest_loss:.4f}, which is very low. "
            "This may indicate the model is memorising the training data. "
            "Evaluate on a held-out set to confirm generalisation."
        ),
        evidence=[
            {
                "type": "metric",
                "reference_id": "train_loss",
                "label": "Current training loss",
                "value": round(latest_loss, 4),
            }
        ],
        provider="rule_engine",
        expected_effect=(
            "Evaluation on held-out data will confirm whether generalisation is intact."
        ),
        tradeoffs="No config change suggested — this is an informational signal.",
        confidence=0.6,
        risk_level="low",
    )


def _check_high_truncation(
    grouped: dict[str, list[tuple[int, float]]],
    current_max_seq_length: int,
) -> AISuggestionCreate | None:
    series = grouped.get("truncation_rate")
    if not series:
        return None

    latest_rate = series[-1][1]
    if latest_rate <= 0.20:
        return None

    suggested_seq_length = min(current_max_seq_length * 2, 4096)
    return AISuggestionCreate(
        config_diff={
            "preprocessing.max_seq_length": {
                "current": current_max_seq_length,
                "suggested": suggested_seq_length,
            },
        },
        rationale=(
            f"{latest_rate * 100:.1f}% of training samples are being truncated. "
            "Increasing the maximum sequence length will preserve more context "
            "and reduce information loss during training."
        ),
        evidence=[
            {
                "type": "metric",
                "reference_id": "truncation_rate",
                "label": "Sample truncation rate",
                "value": f"{latest_rate * 100:.1f}%",
            }
        ],
        provider="rule_engine",
        expected_effect="Longer sequences capture more context, improving task performance.",
        tradeoffs="Longer sequences require more GPU memory and increase training time.",
        confidence=0.8,
        risk_level="low",
    )


def _check_memory_limit(
    grouped: dict[str, list[tuple[int, float]]],
    current_batch_size: int,
    current_gradient_checkpointing: bool,
    max_memory_gb: float | None,
) -> AISuggestionCreate | None:
    series = grouped.get("gpu_memory_allocated_mb") or grouped.get("memory_allocated")
    if not series:
        return None

    latest_usage_mb = series[-1][1]
    # Fall back to a generous 16 GB default when no hardware cap is configured
    max_memory_mb = (max_memory_gb * 1024) if max_memory_gb else 16384.0
    if latest_usage_mb <= max_memory_mb * 0.90:
        return None

    diff: dict[str, dict[str, Any]] = {}
    if current_batch_size > 1:
        diff["training.batch_size"] = {
            "current": current_batch_size,
            "suggested": max(1, current_batch_size // 2),
        }
    if not current_gradient_checkpointing:
        diff["optimization.gradient_checkpointing"] = {
            "current": False,
            "suggested": True,
        }

    if not diff:
        return None

    utilisation_pct = latest_usage_mb / max_memory_mb * 100
    return AISuggestionCreate(
        config_diff=diff,
        rationale=(
            f"GPU memory usage is {latest_usage_mb:.0f} MB "
            f"({utilisation_pct:.1f}% of {max_memory_mb:.0f} MB limit), "
            "approaching the limit. Reducing batch size and enabling gradient "
            "checkpointing will reduce peak memory usage."
        ),
        evidence=[
            {
                "type": "metric",
                "reference_id": "gpu_memory_allocated_mb",
                "label": "GPU memory usage (MB)",
                "value": f"{latest_usage_mb:.0f} MB",
            }
        ],
        provider="rule_engine",
        expected_effect="Reduced OOM risk at the cost of slightly slower throughput.",
        tradeoffs=(
            "Smaller batch sizes increase gradient noise. "
            "Gradient checkpointing trades compute for memory."
        ),
        confidence=0.85,
        risk_level="medium",
    )


def evaluate_rules(
    *,
    metrics: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[AISuggestionCreate]:
    """Run all 7 rules and return triggered suggestions."""
    grouped = _group_by_metric(metrics)

    training = config.get("training", {})
    optimization = config.get("optimization", {})
    adapters = config.get("adapters", {})
    preprocessing = config.get("preprocessing", {})
    execution = config.get("execution", {})

    current_lr: float = float(training.get("learning_rate", 2e-4))
    current_epochs: int = int(training.get("epochs", 2))
    current_batch_size: int = int(training.get("batch_size", 4))
    current_max_grad_norm: float = float(training.get("max_grad_norm", 1.0))
    current_max_seq_length: int = int(preprocessing.get("max_seq_length", 512))
    current_warmup_ratio: float = float(optimization.get("warmup_ratio", 0.03))
    current_gradient_checkpointing: bool = bool(optimization.get("gradient_checkpointing", True))
    current_dropout: float = float(adapters.get("dropout", 0.05))
    current_rank: int = int(adapters.get("rank", 8))
    max_memory_gb: float | None = execution.get("max_memory_gb")

    rules = [
        _check_loss_plateau(grouped, current_lr),
        _check_loss_spike(grouped, current_lr, current_warmup_ratio),
        _check_grad_norm_exploding(grouped, current_lr, current_max_grad_norm),
        _check_eval_diverging(grouped, current_epochs, current_dropout, current_rank),
        _check_very_low_loss(grouped),
        _check_high_truncation(grouped, current_max_seq_length),
        _check_memory_limit(
            grouped, current_batch_size, current_gradient_checkpointing, max_memory_gb
        ),
    ]

    return [r for r in rules if r is not None]
