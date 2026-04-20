type Theme = "light" | "dark";
type Density = "compact" | "default" | "cozy";
type Motion = "off" | "subtle" | "default" | "expressive";

type StoredTweaks = {
  theme: Theme;
  density: Density;
  motion: Motion;
};

type ReadStoredParams<T extends string> = {
  key: string;
  allowed: readonly T[];
  fallback: T;
};

const THEME_STORAGE_KEY = "tweaks.theme";
const DENSITY_STORAGE_KEY = "tweaks.density";
const MOTION_STORAGE_KEY = "tweaks.motion";

const THEME_VALUES: readonly Theme[] = ["light", "dark"];
const DENSITY_VALUES: readonly Density[] = ["compact", "default", "cozy"];
const MOTION_VALUES: readonly Motion[] = ["off", "subtle", "default", "expressive"];

const MOTION_SCALE: Record<Motion, string> = {
  off: "0",
  subtle: "0.6",
  default: "1",
  expressive: "1.25",
};

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
      key: THEME_STORAGE_KEY,
      allowed: THEME_VALUES,
      fallback: "light",
    }),
    density: readStored<Density>({
      key: DENSITY_STORAGE_KEY,
      allowed: DENSITY_VALUES,
      fallback: "default",
    }),
    motion: readStored<Motion>({
      key: MOTION_STORAGE_KEY,
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
  root.style.setProperty("--motion-scale", MOTION_SCALE[motion]);
}
