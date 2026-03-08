from __future__ import annotations

from pydantic import BaseModel
from typing import Literal


class ProjectConfig(BaseModel):
    name: str
    description: str = ""
    mode: Literal["single_user_local"] = "single_user_local"


class ModelConfig(BaseModel):
    source: Literal["huggingface", "local"]
    model_id: str
    family: Literal["causal_lm", "seq2seq", "encoder_only"] = "causal_lm"
    revision: str = "main"
    trust_remote_code: bool = False
    torch_dtype: Literal["auto", "float16", "bfloat16", "float32"] = "auto"


class DatasetConfig(BaseModel):
    source: Literal["huggingface", "local_jsonl", "local_csv", "custom"]
    dataset_id: str
    train_split: str = "train"
    eval_split: str | None = "validation"
    input_field: str = "prompt"
    target_field: str = "response"
    format: Literal["default", "sharegpt", "openai", "alpaca", "custom"] = "default"
    format_mapping: dict[str, str] | None = None
    filter_expression: str | None = None
    max_samples: int | None = None
    subset: str | None = None


class PreprocessingConfig(BaseModel):
    max_seq_length: int = 512
    truncation: bool = True
    packing: bool = False
    padding: Literal["max_length", "longest", "do_not_pad"] = "longest"


class TrainingConfig(BaseModel):
    task_type: Literal["sft"] = "sft"
    epochs: int = 2
    batch_size: int = 4
    gradient_accumulation_steps: int = 4
    learning_rate: float = 2e-4
    weight_decay: float = 0.01
    max_grad_norm: float = 1.0
    eval_steps: int = 50
    save_steps: int = 100
    logging_steps: int = 10
    seed: int = 42
    resume_from_checkpoint: str | None = None


class OptimizationConfig(BaseModel):
    optimizer: Literal["adamw", "adam", "sgd", "adafactor", "paged_adamw_8bit"] = "adamw"
    scheduler: Literal[
        "cosine",
        "linear",
        "constant",
        "constant_with_warmup",
        "cosine_with_restarts",
    ] = "cosine"
    warmup_ratio: float = 0.03
    warmup_steps: int = 0
    gradient_checkpointing: bool = True
    mixed_precision: Literal["no", "fp16", "bf16"] = "bf16"


class AdaptersConfig(BaseModel):
    enabled: bool = True
    type: Literal["lora", "qlora"] = "lora"
    rank: int = 8
    alpha: int = 16
    dropout: float = 0.05
    target_modules: list[str] = ["q_proj", "v_proj"]
    bias: Literal["none", "all", "lora_only"] = "none"
    task_type: Literal["CAUSAL_LM", "SEQ_2_SEQ_LM"] = "CAUSAL_LM"


class QuantizationConfig(BaseModel):
    enabled: bool = False
    mode: Literal["4bit", "8bit"] = "4bit"
    compute_dtype: Literal["float16", "bfloat16"] = "bfloat16"
    quant_type: Literal["nf4", "fp4"] = "nf4"
    double_quant: bool = True


class ObservabilityConfig(BaseModel):
    log_every_steps: int = 10
    capture_grad_norm: bool = True
    capture_memory: bool = True
    capture_activation_samples: bool = True
    capture_weight_deltas: bool = True
    observability_level: Literal["minimal", "standard", "deep", "expert"] = "standard"


class AIAssistantConfig(BaseModel):
    enabled: bool = True
    provider: Literal["anthropic", "openai_compatible"] = "anthropic"
    mode: Literal["suggest_only", "suggest_and_draft"] = "suggest_only"
    allow_config_diffs: bool = True
    auto_analyze_on_completion: bool = True


class ExecutionConfig(BaseModel):
    device: Literal["auto", "cuda", "mps", "cpu"] = "auto"
    max_memory_gb: float | None = None
    num_workers: int = 2


class CheckpointRetentionConfig(BaseModel):
    keep_last_n: int = 3
    always_keep_best_eval: bool = True
    always_keep_final: bool = True
    delete_intermediates_after_completion: bool = True


class IntrospectionConfig(BaseModel):
    architecture_view: bool = True
    editable_weight_scope: Literal["disabled", "bounded_expert_mode"] = "bounded_expert_mode"
    activation_probe_samples: int = 3
    activation_storage: Literal["summary_only", "on_demand_full"] = "summary_only"


class WorkbenchConfig(BaseModel):
    """Top-level config validated by Pydantic."""

    project: ProjectConfig
    model: ModelConfig
    dataset: DatasetConfig
    preprocessing: PreprocessingConfig
    training: TrainingConfig
    optimization: OptimizationConfig
    adapters: AdaptersConfig
    quantization: QuantizationConfig
    observability: ObservabilityConfig
    ai_assistant: AIAssistantConfig
    execution: ExecutionConfig
    checkpoint_retention: CheckpointRetentionConfig
    introspection: IntrospectionConfig
