export type ConfigSourceTag = "user" | "ai_suggestion" | "system";
export type ModelSource = "huggingface" | "local";
export type ModelFamily = "causal_lm" | "seq2seq" | "encoder_only";
export type TorchDtype = "auto" | "float16" | "bfloat16" | "float32";
export type DatasetSource = "huggingface" | "local_jsonl" | "local_csv" | "custom";
export type DatasetFormat = "default" | "sharegpt" | "openai" | "alpaca" | "custom";
export type PaddingStrategy = "max_length" | "longest" | "do_not_pad";
export type TaskType = "sft";
export type OptimizerType = "adamw" | "adam" | "sgd" | "adafactor" | "paged_adamw_8bit";
export type SchedulerType =
  | "cosine"
  | "linear"
  | "constant"
  | "constant_with_warmup"
  | "cosine_with_restarts";
export type MixedPrecisionMode = "no" | "fp16" | "bf16";
export type AdapterType = "lora" | "qlora";
export type BiasMode = "none" | "all" | "lora_only";
export type PeftTaskType = "CAUSAL_LM" | "SEQ_2_SEQ_LM";
export type QuantMode = "4bit" | "8bit";
export type QuantType = "nf4" | "fp4";
export type QuantComputeDtype = "float16" | "bfloat16";
export type ObservabilityLevel = "minimal" | "standard" | "deep" | "expert";
export type AIProvider = "anthropic" | "openai_compatible";
export type AIMode = "suggest_only" | "suggest_and_draft";
export type DeviceType = "auto" | "cuda" | "mps" | "cpu";
export type ActivationStorageMode = "summary_only" | "on_demand_full";
export type EditableWeightScope = "disabled" | "bounded_expert_mode";
export type ProjectMode = "single_user_local";

export interface ProjectConfig {
  readonly name: string;
  readonly description: string;
  readonly mode: ProjectMode;
}

export interface ModelConfig {
  readonly source: ModelSource;
  readonly modelId: string;
  readonly family: ModelFamily;
  readonly revision: string;
  readonly trustRemoteCode: boolean;
  readonly torchDtype: TorchDtype;
}

export interface DatasetConfig {
  readonly source: DatasetSource;
  readonly datasetId: string;
  readonly trainSplit: string;
  readonly evalSplit: string | null;
  readonly inputField: string;
  readonly targetField: string;
  readonly format: DatasetFormat;
  readonly formatMapping: Record<string, string> | null;
  readonly filterExpression: string | null;
  readonly maxSamples: number | null;
  readonly subset: string | null;
}

export interface PreprocessingConfig {
  readonly maxSeqLength: number;
  readonly truncation: boolean;
  readonly packing: boolean;
  readonly padding: PaddingStrategy;
}

export interface TrainingConfig {
  readonly taskType: TaskType;
  readonly epochs: number;
  readonly batchSize: number;
  readonly gradientAccumulationSteps: number;
  readonly learningRate: number;
  readonly weightDecay: number;
  readonly maxGradNorm: number;
  readonly evalSteps: number;
  readonly saveSteps: number;
  readonly loggingSteps: number;
  readonly seed: number;
  readonly resumeFromCheckpoint: string | null;
}

export interface OptimizationConfig {
  readonly optimizer: OptimizerType;
  readonly scheduler: SchedulerType;
  readonly warmupRatio: number;
  readonly warmupSteps: number;
  readonly gradientCheckpointing: boolean;
  readonly mixedPrecision: MixedPrecisionMode;
}

export interface AdaptersConfig {
  readonly enabled: boolean;
  readonly type: AdapterType;
  readonly rank: number;
  readonly alpha: number;
  readonly dropout: number;
  readonly targetModules: ReadonlyArray<string>;
  readonly bias: BiasMode;
  readonly taskType: PeftTaskType;
}

export interface QuantizationConfig {
  readonly enabled: boolean;
  readonly mode: QuantMode;
  readonly computeDtype: QuantComputeDtype;
  readonly quantType: QuantType;
  readonly doubleQuant: boolean;
}

export interface ObservabilityConfig {
  readonly logEverySteps: number;
  readonly captureGradNorm: boolean;
  readonly captureMemory: boolean;
  readonly captureActivationSamples: boolean;
  readonly captureWeightDeltas: boolean;
  readonly observabilityLevel: ObservabilityLevel;
}

export interface AIAssistantConfig {
  readonly enabled: boolean;
  readonly provider: AIProvider;
  readonly mode: AIMode;
  readonly allowConfigDiffs: boolean;
  readonly autoAnalyzeOnCompletion: boolean;
}

export interface ExecutionConfig {
  readonly device: DeviceType;
  readonly maxMemoryGb: number | null;
  readonly numWorkers: number;
}

export interface CheckpointRetentionConfig {
  readonly keepLastN: number;
  readonly alwaysKeepBestEval: boolean;
  readonly alwaysKeepFinal: boolean;
  readonly deleteIntermediatesAfterCompletion: boolean;
}

export interface IntrospectionConfig {
  readonly architectureView: boolean;
  readonly editableWeightScope: EditableWeightScope;
  readonly activationProbeSamples: number;
  readonly activationStorage: ActivationStorageMode;
}

export interface WorkbenchConfig {
  readonly project: ProjectConfig;
  readonly model: ModelConfig;
  readonly dataset: DatasetConfig;
  readonly preprocessing: PreprocessingConfig;
  readonly training: TrainingConfig;
  readonly optimization: OptimizationConfig;
  readonly adapters: AdaptersConfig;
  readonly quantization: QuantizationConfig;
  readonly observability: ObservabilityConfig;
  readonly aiAssistant: AIAssistantConfig;
  readonly execution: ExecutionConfig;
  readonly checkpointRetention: CheckpointRetentionConfig;
  readonly introspection: IntrospectionConfig;
}

export interface ConfigDiff {
  readonly added: Record<string, unknown>;
  readonly removed: Record<string, unknown>;
  readonly changed: Record<string, { readonly old: unknown; readonly new: unknown }>;
}

export interface ConfigVersion {
  readonly id: string;
  readonly projectId: string;
  readonly versionNumber: number;
  readonly yamlBlob: string;
  readonly yamlHash: string;
  readonly diffFromPrev: ConfigDiff | null;
  readonly sourceTag: ConfigSourceTag;
  readonly sourceDetail: string | null;
  readonly createdAt: string;
}

export interface SaveConfigRequest {
  readonly projectId: string;
  readonly yamlContent: string;
  readonly sourceTag: ConfigSourceTag;
  readonly sourceDetail?: string;
}
