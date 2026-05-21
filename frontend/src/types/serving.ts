export type ServingState = "stopped" | "starting" | "running" | "failed" | "stopping";

export interface ServingStatus {
  readonly project_id: string;
  readonly state: ServingState;
  readonly base_url: string | null;
  readonly model_id: string | null;
  readonly adapter_path: string | null;
  readonly pid: number | null;
  readonly started_at: string | null;
  readonly last_error: string | null;
}

export interface ServingStartResponse {
  readonly status: ServingStatus;
}

export interface ServeRequest {
  readonly serving_model_id?: string;
  readonly run_id?: string;
  readonly trust_remote_code?: boolean;
}
