import * as React from "react";

export interface UseGlobalShortcutsParams {
  readonly onOpenCommandPalette: () => void;
  readonly onToggleSidebar: () => void;
}

export function useGlobalShortcuts({
  onOpenCommandPalette,
  onToggleSidebar,
}: UseGlobalShortcutsParams): void {
  React.useEffect(() => {
    const handleKeydown = (event: KeyboardEvent): void => {
      const hasModifier = event.metaKey || event.ctrlKey;
      if (!hasModifier) return;

      const key = event.key.toLowerCase();
      if (key === "k") {
        event.preventDefault();
        onOpenCommandPalette();
      } else if (event.key === "\\") {
        event.preventDefault();
        onToggleSidebar();
      }
    };

    window.addEventListener("keydown", handleKeydown);
    return () => window.removeEventListener("keydown", handleKeydown);
  }, [onOpenCommandPalette, onToggleSidebar]);
}
