import { ApiError } from "@/api/client";

interface DescribeApiErrorParams {
  readonly cause: unknown;
  readonly fallback: string;
}

export function describeApiError({ cause, fallback }: DescribeApiErrorParams): string {
  if (cause instanceof ApiError && cause.message) return cause.message;
  if (cause instanceof Error && cause.message) return cause.message;
  return fallback;
}
