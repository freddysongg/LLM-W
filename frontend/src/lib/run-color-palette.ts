const PALETTE: ReadonlyArray<string> = [
  "oklch(0.82 0.13 310)",
  "oklch(0.80 0.14 260)",
  "oklch(0.88 0.14 150)",
  "oklch(0.70 0.20 25)",
  "oklch(0.86 0.11 200)",
  "oklch(0.84 0.12 80)",
  "oklch(0.82 0.14 340)",
  "oklch(0.74 0.15 120)",
];

function hashString(input: string): number {
  let hash = 0;
  for (let index = 0; index < input.length; index += 1) {
    hash = (hash * 31 + input.charCodeAt(index)) | 0;
  }
  return Math.abs(hash);
}

export function colorForRunId(runId: string): string {
  const paletteIndex = hashString(runId) % PALETTE.length;
  return PALETTE[paletteIndex];
}
