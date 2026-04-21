export interface ConfigVersionSummary {
  readonly id: string;
  readonly projectId: string;
  readonly versionNumber: number;
  readonly yamlHash: string;
  readonly diffFromPrev: unknown | null;
  readonly sourceTag: string;
  readonly sourceDetail: string | null;
  readonly createdAt: string;
}

export interface ConfigVersionList {
  readonly items: ReadonlyArray<ConfigVersionSummary>;
  readonly total: number;
  readonly limit: number;
  readonly offset: number;
}

export interface ConfigValidationResult {
  readonly isValid: boolean;
  readonly errors: ReadonlyArray<string>;
}
