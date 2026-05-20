import { describe, it, expect, vi } from "vitest";
import { parse as parseYaml } from "yaml";
import { maybeCreateOverrideConfig } from "./runs-page";

const LOCAL_YAML = `
project:
  name: demo
execution:
  device: cpu
  max_memory_gb: null
  num_workers: 0
  environment: local
  modal_gpu_type: null
  data_policy: local_raw
`.trim();

const MODAL_YAML = `
project:
  name: demo
execution:
  device: cuda
  max_memory_gb: null
  num_workers: 0
  environment: modal
  modal_gpu_type: a10
  data_policy: sanitized_cloud
`.trim();

const MODAL_YAML_WITHOUT_DATA_POLICY = `
project:
  name: demo
execution:
  device: cuda
  max_memory_gb: null
  num_workers: 0
  environment: modal
  modal_gpu_type: a10
`.trim();

interface SaveConfigCall {
  readonly request: {
    readonly projectId: string;
    readonly yamlContent: string;
    readonly sourceTag: string;
    readonly sourceDetail?: string;
  };
}

function makeSaveConfig(): {
  readonly mock: ReturnType<typeof vi.fn>;
  readonly fn: (params: SaveConfigCall) => Promise<{ readonly id: string }>;
} {
  const mock = vi.fn(async () => ({ id: "cv-new" }));
  return {
    mock,
    fn: mock as unknown as (params: SaveConfigCall) => Promise<{ readonly id: string }>,
  };
}

describe("maybeCreateOverrideConfig", () => {
  it("returns null when picker matches the active config (local→local)", async () => {
    const { mock, fn } = makeSaveConfig();
    const result = await maybeCreateOverrideConfig({
      projectId: "p1",
      activeConfig: { id: "cv1", yamlBlob: LOCAL_YAML },
      environment: "local",
      modalGpuType: null,
      saveConfig: fn,
    });
    expect(result).toBeNull();
    expect(mock).not.toHaveBeenCalled();
  });

  it("returns null when picker matches the active config (modal+a10)", async () => {
    const { mock, fn } = makeSaveConfig();
    const result = await maybeCreateOverrideConfig({
      projectId: "p1",
      activeConfig: { id: "cv1", yamlBlob: MODAL_YAML },
      environment: "modal",
      modalGpuType: "a10",
      saveConfig: fn,
    });
    expect(result).toBeNull();
    expect(mock).not.toHaveBeenCalled();
  });

  it("saves a new version when environment changes (local→modal) and forces sanitized_cloud", async () => {
    const { mock, fn } = makeSaveConfig();
    const result = await maybeCreateOverrideConfig({
      projectId: "p1",
      activeConfig: { id: "cv1", yamlBlob: LOCAL_YAML },
      environment: "modal",
      modalGpuType: "h100",
      saveConfig: fn,
    });
    expect(result).toBe("cv-new");
    expect(mock).toHaveBeenCalledTimes(1);
    const call = mock.mock.calls[0][0] as SaveConfigCall;
    const patched = parseYaml(call.request.yamlContent);
    expect(patched.execution.environment).toBe("modal");
    expect(patched.execution.modal_gpu_type).toBe("h100");
    // Backend _validate_execution_for_run rejects modal + local_raw outright,
    // so the override must rewrite data_policy to sanitized_cloud on switch.
    expect(patched.execution.data_policy).toBe("sanitized_cloud");
  });

  it("rewrites a modal config that is missing data_policy", async () => {
    const { mock, fn } = makeSaveConfig();
    const result = await maybeCreateOverrideConfig({
      projectId: "p1",
      activeConfig: { id: "cv1", yamlBlob: MODAL_YAML_WITHOUT_DATA_POLICY },
      environment: "modal",
      modalGpuType: "a10",
      saveConfig: fn,
    });
    expect(result).toBe("cv-new");
    const call = mock.mock.calls[0][0] as SaveConfigCall;
    const patched = parseYaml(call.request.yamlContent);
    expect(patched.execution.data_policy).toBe("sanitized_cloud");
  });

  it("preserves local_raw when reverting modal→local", async () => {
    const { mock, fn } = makeSaveConfig();
    await maybeCreateOverrideConfig({
      projectId: "p1",
      activeConfig: { id: "cv1", yamlBlob: MODAL_YAML },
      environment: "local",
      modalGpuType: null,
      saveConfig: fn,
    });
    const call = mock.mock.calls[0][0] as SaveConfigCall;
    const patched = parseYaml(call.request.yamlContent);
    // The saved config had sanitized_cloud (modal); reverting to local keeps
    // whatever the user had previously declared — we don't downgrade to
    // local_raw because that decision belongs to the dataset/policy editor.
    expect(patched.execution.data_policy).toBe("sanitized_cloud");
  });

  it("preserves modal_gpu_type when switching modal→local", async () => {
    const { mock, fn } = makeSaveConfig();
    const result = await maybeCreateOverrideConfig({
      projectId: "p1",
      activeConfig: { id: "cv1", yamlBlob: MODAL_YAML },
      environment: "local",
      modalGpuType: null,
      saveConfig: fn,
    });
    expect(result).toBe("cv-new");
    const call = mock.mock.calls[0][0] as SaveConfigCall;
    const patched = parseYaml(call.request.yamlContent);
    expect(patched.execution.environment).toBe("local");
    // The backend rejects modal_gpu_type=null; preserve the existing value
    // so the patched config still validates even though the run won't use it.
    expect(patched.execution.modal_gpu_type).toBe("a10");
  });

  it("does not save a new version when only switching modal→local with same gpu", async () => {
    const { mock, fn } = makeSaveConfig();
    // env change still triggers a save, but the gpu mismatch alone (when target is local)
    // must not bypass the equality check — gpu_changed is irrelevant for local target.
    const result = await maybeCreateOverrideConfig({
      projectId: "p1",
      activeConfig: { id: "cv1", yamlBlob: MODAL_YAML },
      environment: "local",
      modalGpuType: "h100",
      saveConfig: fn,
    });
    expect(result).toBe("cv-new");
    expect(mock).toHaveBeenCalledTimes(1);
    const call = mock.mock.calls[0][0] as SaveConfigCall;
    const patched = parseYaml(call.request.yamlContent);
    // The picker's "h100" is ignored when target is local; existing a10 wins.
    expect(patched.execution.modal_gpu_type).toBe("a10");
  });

  it("saves a new version when GPU changes within modal", async () => {
    const { mock, fn } = makeSaveConfig();
    const result = await maybeCreateOverrideConfig({
      projectId: "p1",
      activeConfig: { id: "cv1", yamlBlob: MODAL_YAML },
      environment: "modal",
      modalGpuType: "h100",
      saveConfig: fn,
    });
    expect(result).toBe("cv-new");
    const call = mock.mock.calls[0][0] as SaveConfigCall;
    const patched = parseYaml(call.request.yamlContent);
    expect(patched.execution.modal_gpu_type).toBe("h100");
  });

  it("preserves unrelated config fields when patching execution", async () => {
    const { mock, fn } = makeSaveConfig();
    await maybeCreateOverrideConfig({
      projectId: "p1",
      activeConfig: { id: "cv1", yamlBlob: MODAL_YAML },
      environment: "local",
      modalGpuType: null,
      saveConfig: fn,
    });
    const call = mock.mock.calls[0][0] as SaveConfigCall;
    const patched = parseYaml(call.request.yamlContent);
    expect(patched.project.name).toBe("demo");
  });
});
