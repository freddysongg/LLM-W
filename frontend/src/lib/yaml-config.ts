type JsonValue = string | number | boolean | null | JsonValue[] | JsonObject;
type JsonObject = { [key: string]: JsonValue };

function snakeToCamelKey(key: string): string {
  return key.replace(/_([a-z])/g, (_, char: string) => char.toUpperCase());
}

function camelToSnakeKey(key: string): string {
  // Two-pass replace handles consecutive uppercase (e.g. maxMemoryGb → max_memory_gb).
  // Single-char replace would produce max_memory_g_b.
  return key
    .replace(/([A-Z]+)([A-Z][a-z])/g, "$1_$2")
    .replace(/([a-z\d])([A-Z])/g, "$1_$2")
    .toLowerCase();
}

function deepConvertKeys(
  value: JsonValue,
  convertKey: (key: string) => string,
): JsonValue {
  if (value === null || typeof value !== "object") return value;
  if (Array.isArray(value)) {
    return value.map((item) => deepConvertKeys(item, convertKey));
  }
  // Safe: null and array branches are excluded above, leaving only plain objects.
  const obj = value as JsonObject;
  const result: JsonObject = {};
  for (const key of Object.keys(obj)) {
    result[convertKey(key)] = deepConvertKeys(obj[key], convertKey);
  }
  return result;
}

export function normalizeYamlConfig<T>(parsed: unknown): T {
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`YAML config must be an object, got: ${typeof parsed}`);
  }
  // Safe: guard above confirms parsed is a non-null, non-array object.
  return deepConvertKeys(parsed as JsonValue, snakeToCamelKey) as T;
}

export function denormalizeYamlConfig(config: unknown): unknown {
  if (config === null || typeof config !== "object" || Array.isArray(config)) {
    throw new Error(`Config must be an object, got: ${typeof config}`);
  }
  // Safe: guard above confirms config is a non-null, non-array object.
  return deepConvertKeys(config as JsonValue, camelToSnakeKey);
}
