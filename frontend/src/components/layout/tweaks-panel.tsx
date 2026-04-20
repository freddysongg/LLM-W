import * as React from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/stores/app-store";
import {
  STORAGE_KEYS,
  THEME_VALUES,
  DENSITY_VALUES,
  MOTION_VALUES,
  scaleFor,
  type Theme,
  type Density,
  type Motion,
} from "@/lib/theme-init";

type TweakKind = "theme" | "density" | "motion";

const ACTIVATE_MESSAGE_TYPE = "__activate_edit_mode";
const DEACTIVATE_MESSAGE_TYPE = "__deactivate_edit_mode";

interface EditModeMessage {
  readonly type?: unknown;
}

function hasMessageType(input: unknown): input is EditModeMessage {
  return typeof input === "object" && input !== null;
}

interface ReadStoredValueParams<T extends string> {
  readonly key: string;
  readonly allowed: readonly T[];
  readonly fallback: T;
}

interface PersistValueParams {
  readonly key: string;
  readonly value: string;
}

interface ApplyTweakParams {
  readonly kind: TweakKind;
  readonly value: string;
}

function readStoredValue<T extends string>({
  key,
  allowed,
  fallback,
}: ReadStoredValueParams<T>): T {
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

function persistValue({ key, value }: PersistValueParams): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* non-fatal — tweaks still apply in-memory */
  }
}

function applyTweakToDom({ kind, value }: ApplyTweakParams): void {
  const root = document.documentElement;
  if (kind === "theme") {
    root.setAttribute("data-theme", value);
    return;
  }
  if (kind === "density") {
    root.setAttribute("data-density", value);
    return;
  }
  root.setAttribute("data-motion", value);
  root.style.setProperty("--motion-scale", scaleFor(value as Motion));
}

interface TweakSegProps<T extends string> {
  readonly options: readonly T[];
  readonly value: T;
  readonly onChange: (next: T) => void;
  readonly ariaLabel: string;
}

function TweakSeg<T extends string>({
  options,
  value,
  onChange,
  ariaLabel,
}: TweakSegProps<T>): React.JSX.Element {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className={cn(
        "flex items-center gap-0.5 rounded-md border border-hairline bg-surface-2 p-0.5",
      )}
    >
      {options.map((option) => {
        const isActive = option === value;
        return (
          <button
            key={option}
            type="button"
            role="radio"
            aria-checked={isActive}
            onClick={(): void => onChange(option)}
            className={cn(
              "flex-1 rounded-sm px-2 py-1 font-mono text-[10px] uppercase tracking-[0.08em]",
              "transition-colors",
              isActive
                ? "bg-surface text-ink-1 shadow-token-sm"
                : "bg-transparent text-ink-3 hover:text-ink-1",
            )}
          >
            {option}
          </button>
        );
      })}
    </div>
  );
}

interface TweakRowProps {
  readonly label: string;
  readonly children: React.ReactNode;
}

function TweakRow({ label, children }: TweakRowProps): React.JSX.Element {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">{label}</span>
      {children}
    </div>
  );
}

export function TweaksPanel(): React.JSX.Element | null {
  const isOpen = useAppStore((state) => state.isTweaksPanelOpen);
  const setTweaksPanelOpen = useAppStore((state) => state.setTweaksPanelOpen);

  const [theme, setThemeState] = React.useState<Theme>(() =>
    readStoredValue<Theme>({
      key: STORAGE_KEYS.theme,
      allowed: THEME_VALUES,
      fallback: "light",
    }),
  );
  const [density, setDensityState] = React.useState<Density>(() =>
    readStoredValue<Density>({
      key: STORAGE_KEYS.density,
      allowed: DENSITY_VALUES,
      fallback: "default",
    }),
  );
  const [motion, setMotionState] = React.useState<Motion>(() =>
    readStoredValue<Motion>({
      key: STORAGE_KEYS.motion,
      allowed: MOTION_VALUES,
      fallback: "default",
    }),
  );

  React.useEffect(() => {
    const handleMessage = (event: MessageEvent): void => {
      if (!hasMessageType(event.data)) return;
      const { type } = event.data;
      if (type === ACTIVATE_MESSAGE_TYPE) {
        setTweaksPanelOpen(true);
      } else if (type === DEACTIVATE_MESSAGE_TYPE) {
        setTweaksPanelOpen(false);
      }
    };
    window.addEventListener("message", handleMessage);
    return (): void => window.removeEventListener("message", handleMessage);
  }, [setTweaksPanelOpen]);

  const handleThemeChange = React.useCallback((next: Theme): void => {
    setThemeState(next);
    applyTweakToDom({ kind: "theme", value: next });
    persistValue({ key: STORAGE_KEYS.theme, value: next });
  }, []);

  const handleDensityChange = React.useCallback((next: Density): void => {
    setDensityState(next);
    applyTweakToDom({ kind: "density", value: next });
    persistValue({ key: STORAGE_KEYS.density, value: next });
  }, []);

  const handleMotionChange = React.useCallback((next: Motion): void => {
    setMotionState(next);
    applyTweakToDom({ kind: "motion", value: next });
    persistValue({ key: STORAGE_KEYS.motion, value: next });
  }, []);

  const handleClose = React.useCallback((): void => {
    setTweaksPanelOpen(false);
  }, [setTweaksPanelOpen]);

  if (!isOpen) return null;

  return (
    <aside
      aria-label="Tweaks"
      className={cn(
        "fixed bottom-4 right-4 z-[180] w-[280px] overflow-hidden",
        "rounded-lg border border-hairline bg-surface shadow-token-lg",
        "animate-fade-up",
      )}
    >
      <header
        className={cn(
          "flex items-center justify-between border-b border-hairline px-3.5 py-2.5",
          "font-mono text-[12px] font-semibold text-ink-1",
        )}
      >
        <span>Tweaks</span>
        <button
          type="button"
          onClick={handleClose}
          aria-label="Close tweaks panel"
          className={cn(
            "inline-grid h-6 w-6 place-items-center rounded-sm text-ink-3",
            "transition-colors hover:bg-surface-2 hover:text-ink-1",
            "focus:outline-none focus-visible:[box-shadow:var(--focus-ring)]",
          )}
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </header>
      <div className="flex flex-col gap-3 px-3.5 py-3">
        <TweakRow label="Theme">
          <TweakSeg<Theme>
            options={THEME_VALUES}
            value={theme}
            onChange={handleThemeChange}
            ariaLabel="Theme"
          />
        </TweakRow>
        <TweakRow label="Motion">
          <TweakSeg<Motion>
            options={MOTION_VALUES}
            value={motion}
            onChange={handleMotionChange}
            ariaLabel="Motion"
          />
        </TweakRow>
        <TweakRow label="Density">
          <TweakSeg<Density>
            options={DENSITY_VALUES}
            value={density}
            onChange={handleDensityChange}
            ariaLabel="Density"
          />
        </TweakRow>
      </div>
    </aside>
  );
}
