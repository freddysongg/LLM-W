import * as React from "react";
import { render, type RenderOptions, type RenderResult } from "@testing-library/react";
import { renderHook, type RenderHookOptions, type RenderHookResult } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

interface ProviderWrapperProps {
  readonly children: React.ReactNode;
}

interface RenderWithProvidersOptions extends Omit<RenderOptions, "wrapper"> {
  readonly queryClient?: QueryClient;
}

interface RenderWithProvidersResult extends RenderResult {
  readonly queryClient: QueryClient;
}

export function renderWithProviders(
  ui: React.ReactElement,
  { queryClient = createTestQueryClient(), ...options }: RenderWithProvidersOptions = {},
): RenderWithProvidersResult {
  const Wrapper = ({ children }: ProviderWrapperProps): React.JSX.Element => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

  const result = render(ui, { wrapper: Wrapper, ...options });
  return { ...result, queryClient };
}

interface RenderHookWithProvidersOptions<TProps> extends Omit<
  RenderHookOptions<TProps>,
  "wrapper"
> {
  readonly queryClient?: QueryClient;
}

interface RenderHookWithProvidersResult<TResult, TProps> extends RenderHookResult<TResult, TProps> {
  readonly queryClient: QueryClient;
}

export function renderHookWithProviders<TResult, TProps>(
  callback: (props: TProps) => TResult,
  {
    queryClient = createTestQueryClient(),
    ...options
  }: RenderHookWithProvidersOptions<TProps> = {},
): RenderHookWithProvidersResult<TResult, TProps> {
  const Wrapper = ({ children }: ProviderWrapperProps): React.JSX.Element => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

  const result = renderHook(callback, { wrapper: Wrapper, ...options });
  return { ...result, queryClient };
}
