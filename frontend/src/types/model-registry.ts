export interface ModelRegistryEntry {
  readonly name: string;
  readonly params: string;
  readonly context: string;
  readonly license: string;
  readonly source: string;
  readonly isPinned: boolean;
}
