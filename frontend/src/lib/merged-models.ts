interface DeriveMergedNameParams {
  readonly baseModelId: string;
  readonly adapterStep: number | null;
}

export function deriveMergedName({ baseModelId, adapterStep }: DeriveMergedNameParams): string {
  const baseLabel = baseModelId.includes("/") ? baseModelId.split("/").pop() : baseModelId;
  const suffix = adapterStep !== null ? `-step${adapterStep}` : "";
  return `${baseLabel}-merged${suffix}`;
}
