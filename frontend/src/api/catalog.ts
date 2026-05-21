import type { ModalGpuOption } from "@/types/catalog";
import type { ModalGpuType } from "@/types/config";
import type { LlmCatalogProvider, LlmModelOption } from "@/types/llm-catalog";
import type { ModelRegistryEntry, RegisterModelEntryRequest } from "@/types/model-registry";
import { ApiError, fetchApi } from "./client";

interface RawModalGpuOption {
  readonly gpu_type: string;
  readonly label: string;
  readonly vram_gb: number;
  readonly rate_usd_hr: number;
}

interface RawModalGpuCatalogResponse {
  readonly options: ReadonlyArray<RawModalGpuOption>;
}

interface RawLlmModelOption {
  readonly provider: string;
  readonly model_id: string;
  readonly label: string;
}

interface RawLlmCatalogResponse {
  readonly options: ReadonlyArray<RawLlmModelOption>;
}

const KNOWN_MODAL_GPU_TYPES: ReadonlySet<ModalGpuType> = new Set<ModalGpuType>([
  "t4",
  "a10",
  "l40s",
  "a100-40gb",
  "a100-80gb",
  "h100",
]);

const KNOWN_LLM_PROVIDERS: ReadonlySet<LlmCatalogProvider> = new Set<LlmCatalogProvider>([
  "openai",
  "anthropic",
]);

function isModalGpuType(value: string): value is ModalGpuType {
  return KNOWN_MODAL_GPU_TYPES.has(value as ModalGpuType);
}

function isLlmCatalogProvider(value: string): value is LlmCatalogProvider {
  return KNOWN_LLM_PROVIDERS.has(value as LlmCatalogProvider);
}

function normalizeOption(raw: RawModalGpuOption): ModalGpuOption {
  const { gpu_type, label, vram_gb, rate_usd_hr } = raw;
  if (!isModalGpuType(gpu_type)) {
    throw new ApiError({
      status: 200,
      statusText: "OK",
      code: "CATALOG_INVALID_GPU_TYPE",
      message: `Unknown modal_gpu_type received from server: ${gpu_type}`,
      details: { gpu_type },
    });
  }
  return {
    gpuType: gpu_type,
    label,
    vramGb: vram_gb,
    rateUsdHr: rate_usd_hr,
  };
}

function normalizeLlmOption(raw: RawLlmModelOption): LlmModelOption {
  const { provider, model_id, label } = raw;
  if (!isLlmCatalogProvider(provider)) {
    throw new ApiError({
      status: 200,
      statusText: "OK",
      code: "CATALOG_INVALID_LLM_PROVIDER",
      message: `Unknown llm provider received from server: ${provider}`,
      details: { provider },
    });
  }
  return { provider, modelId: model_id, label };
}

export async function fetchModalGpus(): Promise<ReadonlyArray<ModalGpuOption>> {
  const raw = await fetchApi<RawModalGpuCatalogResponse>({ path: "/catalog/modal-gpus" });
  return raw.options.map(normalizeOption);
}

export async function fetchLlmModels(): Promise<ReadonlyArray<LlmModelOption>> {
  const raw = await fetchApi<RawLlmCatalogResponse>({ path: "/catalog/llm-models" });
  return raw.options.map(normalizeLlmOption);
}

interface RawModelRegistryEntry {
  readonly name: string;
  readonly source: string;
  readonly is_pinned: boolean;
  readonly params: string | null;
  readonly context: string | null;
  readonly license: string | null;
  readonly path: string | null;
  readonly dtype: string | null;
}

interface RawModelRegistryResponse {
  readonly entries: ReadonlyArray<RawModelRegistryEntry>;
}

function normalizeRegistryEntry(raw: RawModelRegistryEntry): ModelRegistryEntry {
  return {
    name: raw.name,
    source: raw.source,
    isPinned: raw.is_pinned,
    params: raw.params,
    context: raw.context,
    license: raw.license,
    path: raw.path,
    dtype: raw.dtype,
  };
}

export async function fetchModelRegistry(): Promise<ReadonlyArray<ModelRegistryEntry>> {
  const raw = await fetchApi<RawModelRegistryResponse>({ path: "/catalog/model-registry" });
  return raw.entries.map(normalizeRegistryEntry);
}

export async function registerModelEntry({
  request,
}: {
  request: RegisterModelEntryRequest;
}): Promise<ModelRegistryEntry> {
  const raw = await fetchApi<RawModelRegistryEntry>({
    path: "/catalog/model-registry",
    method: "POST",
    body: {
      name: request.name,
      source: request.source,
      path: request.path,
      dtype: request.dtype,
      is_pinned: request.isPinned,
    },
  });
  return normalizeRegistryEntry(raw);
}
