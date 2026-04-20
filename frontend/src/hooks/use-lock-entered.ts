import { useEffect, useState } from "react";

const LOCK_AFTER_MS = 900;

export function useLockEntered(): boolean {
  const [isLocked, setIsLocked] = useState<boolean>(false);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setIsLocked(true);
    }, LOCK_AFTER_MS);
    return () => window.clearTimeout(timeoutId);
  }, []);

  return isLocked;
}
