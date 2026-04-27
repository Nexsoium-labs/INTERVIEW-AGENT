// Centralized platform detection and environment configuration.
// Safe to import from client modules and call during SSR.

export type Platform = "SENTINEL_NODE" | "NEXUS_CLOUD";

export function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export function getPlatform(): Platform {
  return isTauri() ? "SENTINEL_NODE" : "NEXUS_CLOUD";
}

export function getApiBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL;
  }

  return isTauri() ? "http://127.0.0.1:8000" : "";
}
