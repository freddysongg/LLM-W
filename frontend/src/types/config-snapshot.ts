export interface ConfigDiffEntry {
  readonly old: unknown;
  readonly new: unknown;
}

export interface ConfigDiff {
  readonly changed: Readonly<Record<string, ConfigDiffEntry>>;
  readonly added: Readonly<Record<string, unknown>>;
  readonly removed: Readonly<Record<string, unknown>>;
}

export interface ConfigSnapshot {
  readonly runId: string;
  readonly parentConfigVersionId: string;
  readonly yaml: string;
  readonly diff: ConfigDiff;
}
