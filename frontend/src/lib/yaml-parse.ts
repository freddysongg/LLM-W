import { parse, YAMLParseError } from "yaml";

export type YamlParseResult =
  | { readonly ok: true; readonly value: unknown }
  | { readonly ok: false; readonly line: number | null; readonly message: string };

export function tryParseYaml(source: string): YamlParseResult {
  try {
    const value: unknown = parse(source);
    return { ok: true, value };
  } catch (err) {
    if (err instanceof YAMLParseError) {
      const firstLinePos = err.linePos?.[0];
      return {
        ok: false,
        line: firstLinePos ? firstLinePos.line : null,
        message: err.message,
      };
    }
    return {
      ok: false,
      line: null,
      message: err instanceof Error ? err.message : String(err),
    };
  }
}
