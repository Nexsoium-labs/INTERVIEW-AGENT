"use client";

import { useCallback, useEffect, useState } from "react";

import { isTauri } from "@/lib/platform";

export interface AntiCheatState {
  violated: boolean;
  clearViolation: () => void;
}

export function useAntiCheat(): AntiCheatState {
  const [violated, setViolated] = useState(false);

  const clearViolation = useCallback(() => {
    setViolated(false);
  }, []);

  useEffect(() => {
    let unlisten: (() => void) | undefined;
    let disposed = false;

    if (isTauri()) {
      import("@tauri-apps/api/window")
        .then(({ getCurrentWindow }) =>
          getCurrentWindow().onFocusChanged(({ payload: focused }) => {
            if (!focused) {
              setViolated(true);
            }
          })
        )
        .then((unlistenFn) => {
          if (disposed) {
            unlistenFn();
            return;
          }
          unlisten = unlistenFn;
        })
        .catch(() => {
          // Tauri API unavailable in browser-only development.
        });
    } else {
      const handleBlur = () => setViolated(true);
      window.addEventListener("blur", handleBlur);
      unlisten = () => window.removeEventListener("blur", handleBlur);
    }

    return () => {
      disposed = true;
      unlisten?.();
    };
  }, []);

  return { violated, clearViolation };
}
