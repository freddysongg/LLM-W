const API_BASE_URL = "/api/v1";

interface ApiErrorBody {
  readonly error: {
    readonly code: string;
    readonly message: string;
    readonly details: Record<string, unknown>;
  };
}

export class ApiError extends Error {
  readonly status: number;
  readonly statusText: string;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor({
    status,
    statusText,
    code,
    message,
    details,
  }: {
    status: number;
    statusText: string;
    code: string;
    message: string;
    details: Record<string, unknown>;
  }) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.statusText = statusText;
    this.code = code;
    this.details = details;
  }
}

export async function fetchApi<T>({
  path,
  method = "GET",
  body,
}: {
  path: string;
  method?: string;
  body?: unknown;
}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    let code = "UNKNOWN_ERROR";
    let message = response.statusText;
    let details: Record<string, unknown> = {};

    try {
      const errorBody = (await response.json()) as ApiErrorBody;
      code = errorBody.error.code;
      message = errorBody.error.message;
      details = errorBody.error.details;
    } catch {
      // Non-JSON error body — use defaults
    }

    throw new ApiError({
      status: response.status,
      statusText: response.statusText,
      code,
      message,
      details,
    });
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export async function fetchTextApi({ path }: { path: string }): Promise<string> {
  const response = await fetch(`${API_BASE_URL}${path}`);

  if (!response.ok) {
    let code = "UNKNOWN_ERROR";
    let message = response.statusText;
    let details: Record<string, unknown> = {};

    try {
      const errorBody = (await response.json()) as ApiErrorBody;
      code = errorBody.error.code;
      message = errorBody.error.message;
      details = errorBody.error.details;
    } catch {
      // Non-JSON error body — use defaults
    }

    throw new ApiError({
      status: response.status,
      statusText: response.statusText,
      code,
      message,
      details,
    });
  }

  return response.text();
}
