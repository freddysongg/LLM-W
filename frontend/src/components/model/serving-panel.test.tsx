import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { ServingStatusRow } from "./serving-panel";
import { createTestQueryClient, renderWithProviders } from "@/test-utils";
import type { ServingState, ServingStatus } from "@/types/serving";

const PROJECT_ID = "proj-123";
const BASE_URL = "http://127.0.0.1:8001";

interface StateDisplayExpectation {
  readonly state: ServingState;
  readonly expectedLabel: string;
}

const STATE_LABEL_CASES: ReadonlyArray<StateDisplayExpectation> = [
  { state: "stopped", expectedLabel: "Not serving" },
  { state: "starting", expectedLabel: "Starting model load…" },
  { state: "stopping", expectedLabel: "Stopping…" },
];

function buildStatus({ state }: { state: ServingState }): ServingStatus {
  return {
    project_id: PROJECT_ID,
    state,
    base_url: null,
    model_id: null,
    adapter_path: null,
    pid: null,
    started_at: null,
    last_error: null,
  };
}

function renderRowWithStatus({ status }: { status: ServingStatus }): void {
  const queryClient = createTestQueryClient();
  queryClient.setQueryData(["projects", PROJECT_ID, "serving"], status);
  renderWithProviders(<ServingStatusRow projectId={PROJECT_ID} />, { queryClient });
}

describe("ServingStatusRow", () => {
  it.each(STATE_LABEL_CASES)(
    "renders the '$expectedLabel' label when state is $state",
    ({ state, expectedLabel }) => {
      renderRowWithStatus({ status: buildStatus({ state }) });

      expect(screen.getByText(expectedLabel)).toBeInTheDocument();
    },
  );

  it("appends the base URL to the running label", () => {
    const status: ServingStatus = { ...buildStatus({ state: "running" }), base_url: BASE_URL };
    renderRowWithStatus({ status });

    expect(screen.getByText(`Running · ${BASE_URL}`)).toBeInTheDocument();
  });

  it("renders the last-error message when state is failed", () => {
    const status: ServingStatus = {
      ...buildStatus({ state: "failed" }),
      last_error: "model load oom",
    };
    renderRowWithStatus({ status });

    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("model load oom")).toBeInTheDocument();
  });
});
