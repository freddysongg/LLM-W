import { describe, it, expect, beforeAll, afterAll, afterEach } from "vitest";
import { act, waitFor } from "@testing-library/react";
import { http, HttpResponse, type PathParams } from "msw";
import { setupServer } from "msw/node";
import { useSanitizeProjectDataset } from "./useDatasetProfile";
import { renderHookWithProviders } from "@/test-utils";
import type { SanitizeDatasetRequest } from "@/types/dataset";

const PROJECT_ID = "proj-abc";
const SANITIZE_PATH = `*/api/v1/projects/${PROJECT_ID}/datasets/sanitize`;

const SUCCESS_RESPONSE = {
  total_rows: 100,
  sanitized_rows: [],
  manifest: {
    per_pattern: { email: 3, phone: 2 },
    total_redactions: 5,
  },
  splits: {
    assignments: { "0": "train", "1": "val", "2": "test" },
    counts: { train: 80, val: 10, test: 10 },
  },
  content_hash: "sha256:deadbeef",
  source_format: "openai",
  normalized: true,
};

const ERROR_RESPONSE = {
  error: {
    code: "SANITIZE_FAILED",
    message: "Sanitization failed on row 12",
    details: {},
  },
};

const SAMPLE_REQUEST: SanitizeDatasetRequest = {
  splitRatios: { train: 80, val: 10, test: 10 },
  sourceFormat: "openai",
  normalize: true,
  persist: false,
};

type SanitizeRequestBody = {
  split_ratios: { train: number; val: number; test: number };
  source_format: string;
  normalize: boolean;
  persist: boolean;
};

const server = setupServer();

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

afterEach(() => {
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});

describe("useSanitizeProjectDataset", () => {
  it("posts to the sanitize endpoint and returns a normalized response", async () => {
    let observedBody: SanitizeRequestBody | null = null;
    server.use(
      http.post<PathParams, SanitizeRequestBody>(SANITIZE_PATH, async ({ request }) => {
        observedBody = (await request.json()) as SanitizeRequestBody;
        return HttpResponse.json(SUCCESS_RESPONSE);
      }),
    );

    const { result } = renderHookWithProviders(() =>
      useSanitizeProjectDataset({ projectId: PROJECT_ID }),
    );

    await act(async () => {
      await result.current.mutateAsync(SAMPLE_REQUEST);
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(observedBody).toEqual({
      split_ratios: { train: 80, val: 10, test: 10 },
      source_format: "openai",
      normalize: true,
      persist: false,
    });

    const data = result.current.data;
    expect(data).toBeDefined();
    expect(data?.totalRows).toBe(100);
    expect(data?.manifest.totalRedactions).toBe(5);
    expect(data?.manifest.perPattern).toEqual({ email: 3, phone: 2 });
    expect(data?.contentHash).toBe("sha256:deadbeef");
  });

  it("surfaces a 500 response as a mutation error", async () => {
    server.use(
      http.post(SANITIZE_PATH, () => {
        return HttpResponse.json(ERROR_RESPONSE, { status: 500 });
      }),
    );

    const { result } = renderHookWithProviders(() =>
      useSanitizeProjectDataset({ projectId: PROJECT_ID }),
    );

    await act(async () => {
      await expect(result.current.mutateAsync(SAMPLE_REQUEST)).rejects.toThrow();
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    const error = result.current.error;
    expect(error).toBeInstanceOf(Error);
    expect((error as Error).message).toBe("Sanitization failed on row 12");
  });
});
