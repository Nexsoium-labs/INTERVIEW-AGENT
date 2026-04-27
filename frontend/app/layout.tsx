"use client";

import "./globals.css";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { invoke } from "@tauri-apps/api/core";

import { BackendGate } from "@/components/BackendGate";
import { TitleBar } from "@/components/TitleBar";
import { useOtaUpdater } from "@/lib/hooks/useOtaUpdater";

function detectTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  const router = useRouter();
  const pathname = usePathname();
  const [firstRunChecked, setFirstRunChecked] = useState(false);
  const [tauriRuntime, setTauriRuntime] = useState(false);
  const [bootError, setBootError] = useState("");
  const { updateAvailable, updateProgress } = useOtaUpdater();

  useEffect(() => {
    let cancelled = false;

    async function bootDesktopRuntime() {
      const isTauri = detectTauri();
      setTauriRuntime(isTauri);
      setBootError("");

      if (!isTauri || pathname === "/setup") {
        setFirstRunChecked(true);
        return;
      }

      setFirstRunChecked(false);

      try {
        const isFirstRun = await invoke<boolean>("check_first_run");

        if (cancelled) {
          return;
        }

        if (isFirstRun) {
          setFirstRunChecked(true);
          router.replace("/setup");
          return;
        }

        const SIDECAR_TIMEOUT_MS = 30_000;
        const sidecarPromise = invoke("spawn_returning_sidecar");
        const timeoutPromise = new Promise<never>((_, reject) =>
          setTimeout(
            () => reject(new Error("Backend sidecar spawn timed out after 30 s")),
            SIDECAR_TIMEOUT_MS,
          ),
        );

        await Promise.race([sidecarPromise, timeoutPromise]);
        console.info("Returning sidecar ignition completed.");

        if (!cancelled) {
          setFirstRunChecked(true);
        }
      } catch (err: unknown) {
        if (cancelled) {
          return;
        }

        console.error("Failed to ignite returning sidecar:", err);
        setBootError(
          `Failed to ignite backend sidecar: ${err instanceof Error ? err.message : String(err)
          }`
        );
        setFirstRunChecked(true);
      }
    }

    void bootDesktopRuntime();

    return () => {
      cancelled = true;
    };
  }, [pathname, router]);

  return (
    <html lang="en">
      <body className="h-screen overflow-hidden bg-[#0a0a0a] text-slate-100 flex flex-col">
        {tauriRuntime ? <TitleBar /> : null}
        <main className="min-h-0 flex-1 overflow-hidden [&>*]:!h-full">
          {bootError ? (
            <div className="h-screen w-full flex items-center justify-center bg-[#0a0a0a] px-6">
              <div className="max-w-lg space-y-4 text-center">
                <h1 className="text-xl font-semibold text-rose-300">
                  Backend ignition failed
                </h1>
                <p className="text-sm leading-6 text-slate-400">{bootError}</p>
              </div>
            </div>
          ) : firstRunChecked ? (
            pathname === "/setup" ? (
              children
            ) : (
              <BackendGate>{children}</BackendGate>
            )
          ) : (
            <div className="h-screen w-full flex items-center justify-center bg-[#0a0a0a]">
              <div className="h-8 w-8 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
            </div>
          )}
        </main>

        {updateAvailable && (
          <div className="fixed inset-0 z-[100] flex flex-col items-center justify-center gap-8 bg-[#0a0a0a]/95 backdrop-blur-lg">
            <div className="relative flex items-center justify-center">
              <div className="absolute h-32 w-32 rounded-full bg-cyan-400/5 animate-pulse shadow-[0_0_60px_rgba(34,211,238,0.15)]" />
              <div className="absolute h-24 w-24 rounded-full border border-cyan-500/20 animate-ping" />
              <div className="relative h-20 w-20 rounded-full border border-cyan-400/40 bg-cyan-400/10 flex items-center justify-center">
                <div className="h-3 w-3 rounded-full bg-cyan-400 shadow-[0_0_20px_rgba(34,211,238,1)] animate-pulse" />
              </div>
            </div>

            <div className="text-center space-y-2">
              <h2 className="text-xl font-semibold tracking-widest uppercase text-white">
                Synchronizing Neural Weights
              </h2>
              <p className="text-xs text-slate-500 tracking-widest uppercase">
                System update in progress - do not close the application
              </p>
            </div>

            <div className="w-64 space-y-2">
              <div className="h-1 rounded-full bg-slate-800 overflow-hidden">
                <div
                  className="h-full bg-cyan-500 rounded-full transition-all duration-300 shadow-[0_0_8px_rgba(34,211,238,0.6)]"
                  style={{
                    width: `${updateProgress !== null ? updateProgress : 0}%`,
                  }}
                />
              </div>
              <p className="text-xs text-slate-600 text-center font-mono">
                {updateProgress !== null
                  ? `${updateProgress}%`
                  : "Connecting..."}
              </p>
            </div>
          </div>
        )}
      </body>
    </html>
  );
}
