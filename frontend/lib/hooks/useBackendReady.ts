"use client";

import { useEffect, useState } from "react";

import { getApiBaseUrl, isTauri } from "@/lib/platform";

const MAX_ATTEMPTS = 40;
const POLL_INTERVAL_MS = 500;

export interface BackendReadyState {
  ready: boolean;
  attempts: number;
  error: string | null;
  maxAttempts: number;
}

export function useBackendReady(): BackendReadyState {
  const [ready, setReady] = useState(false);
  const [attempts, setAttempts] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isTauri() && !process.env.NEXT_PUBLIC_API_BASE_URL) {
      setReady(true);
      return;
    }

    const backendUrl = getApiBaseUrl();
    let cancelled = false;
    let attempt = 0;

    async function poll() {
      while (!cancelled && attempt < MAX_ATTEMPTS) {
        try {
          const res = await fetch(`${backendUrl}/api/health`, {
            signal: AbortSignal.timeout(1_000)
          });
          if (res.ok && !cancelled) {
            setReady(true);
            return;
          }
        } catch {
          // Backend sidecar is still starting.
        }

        attempt += 1;
        if (!cancelled) {
          setAttempts(attempt);
        }
        await new Promise<void>((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
      }

      if (!cancelled) {
        setError("Sentinel Node failed to initialize. Please restart the application.");
      }
    }

    poll();
    return () => {
      cancelled = true;
    };
  }, []);

  return { ready, attempts, error, maxAttempts: MAX_ATTEMPTS };
}
