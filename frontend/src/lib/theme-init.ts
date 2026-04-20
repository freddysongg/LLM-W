export type Theme = "light" | "dark";
export type Density = "compact" | "default" | "cozy";
export type Motion = "off" | "subtle" | "default" | "expressive";

interface StoredTweaks {
  readonly theme: Theme;
  readonly density: Density;
  readonly motion: Motion;
}

interface ReadStoredParams<T extends string> {
  readonly key: string;
  readonly allowed: readonly T[];
  readonly fallback: T;
}

export const STORAGE_KEYS = {
  theme: "tweaks.theme",
  density: "tweaks.density",
  motion: "tweaks.motion",
} as const;

export const THEME_VALUES: readonly Theme[] = ["light", "dark"];
export const DENSITY_VALUES: readonly Density[] = ["compact", "default", "cozy"];
export const MOTION_VALUES: readonly Motion[] = ["off", "subtle", "default", "expressive"];

const MOTION_SCALE: Record<Motion, string> = {
  off: "0",
  subtle: "0.6",
  default: "1",
  expressive: "1.25",
};

export function scaleFor(motion: Motion): string {
  return MOTION_SCALE[motion];
}

function readStored<T extends string>({ key, allowed, fallback }: ReadStoredParams<T>): T {
  try {
    const raw = window.localStorage.getItem(key);
    if (raw !== null && (allowed as readonly string[]).includes(raw)) {
      return raw as T;
    }
    return fallback;
  } catch {
    return fallback;
  }
}

function readTweaks(): StoredTweaks {
  return {
    theme: readStored<Theme>({
      key: STORAGE_KEYS.theme,
      allowed: THEME_VALUES,
      fallback: "light",
    }),
    density: readStored<Density>({
      key: STORAGE_KEYS.density,
      allowed: DENSITY_VALUES,
      fallback: "default",
    }),
    motion: readStored<Motion>({
      key: STORAGE_KEYS.motion,
      allowed: MOTION_VALUES,
      fallback: "default",
    }),
  };
}

export function initTheme(): void {
  if (typeof document === "undefined") {
    return;
  }
  const { theme, density, motion } = readTweaks();
  const root = document.documentElement;
  root.setAttribute("data-theme", theme);
  root.setAttribute("data-density", density);
  root.setAttribute("data-motion", motion);
  root.style.setProperty("--motion-scale", scaleFor(motion));
}
