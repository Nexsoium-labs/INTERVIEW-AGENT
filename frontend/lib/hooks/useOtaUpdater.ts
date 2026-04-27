"use client";

import { useEffect, useState } from "react";

import { isTauri } from "@/lib/platform";

export interface OtaUpdaterState {
  updateAvailable: boolean;
  updateProgress: number | null;
}

export function useOtaUpdater(): OtaUpdaterState {
  const [updateAvailable, setUpdateAvailable] = useState(false);
  const [updateProgress, setUpdateProgress] = useState<number | null>(null);

  useEffect(() => {
    if (!isTauri()) return;

    let cancelled = false;

    async function checkAndApply() {
      try {
        const { check } = await import("@tauri-apps/plugin-updater");
        const { relaunch } = await import("@tauri-apps/plugin-process");

        const update = await check();
        if (!update || cancelled) return;

        setUpdateAvailable(true);
        setUpdateProgress(0);

        let downloaded = 0;
        let contentLength = 0;

        await update.downloadAndInstall((event) => {
          if (cancelled) return;

          switch (event.event) {
            case "Started":
              contentLength = event.data.contentLength ?? 0;
              setUpdateProgress(0);
              break;
            case "Progress":
              downloaded += event.data.chunkLength;
              if (contentLength > 0) {
                setUpdateProgress(
                  Math.min(100, Math.round((downloaded / contentLength) * 100))
                );
              }
              break;
            case "Finished":
              setUpdateProgress(100);
              break;
          }
        });

        if (!cancelled) {
          await relaunch();
        }
      } catch {
        if (!cancelled) {
          setUpdateAvailable(false);
          setUpdateProgress(null);
        }
      }
    }

    void checkAndApply();
    return () => {
      cancelled = true;
    };
  }, []);

  return { updateAvailable, updateProgress };
}
