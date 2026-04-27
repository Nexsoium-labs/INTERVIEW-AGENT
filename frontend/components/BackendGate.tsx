"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { AlertCircle, Shield } from "lucide-react";

import { useBackendReady } from "@/lib/hooks/useBackendReady";

export function BackendGate({ children }: { children: ReactNode }) {
  const { ready, attempts, error, maxAttempts } = useBackendReady();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    if (!ready) return;

    const id = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(id);
  }, [ready]);

  if (error) {
    return (
      <div className="h-screen w-full flex items-center justify-center bg-[#0a0a0a]">
        <div className="max-w-sm text-center space-y-4 px-6">
          <AlertCircle className="h-10 w-10 text-rose-400 mx-auto" />
          <h2 className="text-lg font-semibold text-white">
            Initialization Failed
          </h2>
          <p className="text-sm text-slate-400">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-2 px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-sm text-slate-200 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!ready) {
    return (
      <div className="h-screen w-full flex items-center justify-center bg-[#0a0a0a]">
        <div className="flex flex-col items-center gap-6">
          <div className="relative flex items-center justify-center">
            <div className="absolute h-24 w-24 rounded-full border border-cyan-400/20 bg-cyan-400/5 animate-pulse shadow-[0_0_40px_rgba(34,211,238,0.2)]" />
            <div className="rounded-full border border-cyan-400/30 bg-cyan-400/10 p-5 relative">
              <Shield className="h-12 w-12 text-cyan-300" />
            </div>
          </div>

          <div className="text-center space-y-2">
            <h1 className="text-xl font-semibold text-white">
              ZT-ATE Sentinel Node
            </h1>
            <p className="text-xs uppercase tracking-widest text-slate-500">
              Initializing Quantum Core...
            </p>
          </div>

          <div className="w-48 h-1 rounded-full bg-slate-800 overflow-hidden">
            <div
              className="h-full bg-cyan-500 rounded-full transition-all duration-300"
              style={{ width: `${(attempts / maxAttempts) * 100}%` }}
            />
          </div>
          <p className="text-xs text-slate-600">
            {attempts}/{maxAttempts} checks
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="h-full transition-opacity duration-500"
      style={{ opacity: mounted ? 1 : 0 }}
    >
      {children}
    </div>
  );
}
