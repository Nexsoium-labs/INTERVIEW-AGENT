"use client";

/**
 * InteractiveSession
 * ------------------
 * Client-side orchestration shell for the candidate workspace.
 *
 * Owns `sandboxLocked` state so the CountdownTimer can signal the SandboxPane
 * through a shared parent. Anti-cheat focus-loss handling locks the sandbox,
 * pauses the timer, and emits a strict non-biometric INTEGRITY_FLAG event.
 */

import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  Cpu,
  ShieldCheck,
  Terminal,
  Lock,
} from "lucide-react";
import { CountdownTimer } from "./CountdownTimer";
import { SandboxPane } from "./SandboxPane";
import { BiometricSentinel } from "./BiometricSentinel";
import { useAntiCheat } from "@/lib/hooks/useAntiCheat";
import { ingestTelemetry } from "@/lib/api";

interface InteractiveSessionProps {
  sessionId: string;
  candidateRole: string;
}

export function InteractiveSession({
  sessionId,
  candidateRole,
}: InteractiveSessionProps) {
  const [sandboxLocked, setSandboxLocked] = useState(false);
  const [isCompiling, setIsCompiling] = useState(false);
  const { violated } = useAntiCheat();

  useEffect(() => {
    if (!violated) return;

    setSandboxLocked(true);
    setIsCompiling(false);

    const token =
      typeof window !== "undefined"
        ? localStorage.getItem("zt_candidate_token")
        : null;

    void ingestTelemetry(
      sessionId,
      {
        event_type: "INTEGRITY_FLAG",
        telemetry: {
          silence_ms: 1,
        },
        raw_payload: {
          reason: "focus_lost",
          source: "anti_cheat_focus_guard_v1",
          timestamp_ms: Date.now(),
        },
      },
      token
    );
  }, [violated, sessionId]);

  const handleTimerExpire = useCallback(() => {
    setSandboxLocked(true);
    setIsCompiling(false);
  }, []);

  const cryptoPrefix = sessionId.split("-")[0] ?? sessionId.slice(0, 8);
  const timerPaused = violated;

  return (
    <div className="flex flex-col h-full w-full relative">
      {violated && (
        <div className="absolute inset-0 z-50 flex flex-col items-center justify-center gap-6 bg-black/90 backdrop-blur-md">
          <div className="rounded-full border border-rose-500/40 bg-rose-500/10 p-6 shadow-[0_0_60px_rgba(244,63,94,0.3)]">
            <AlertTriangle className="h-16 w-16 text-rose-400 drop-shadow-[0_0_20px_rgba(244,63,94,0.8)]" />
          </div>
          <div className="text-center space-y-2">
            <h2 className="text-2xl font-bold tracking-[0.1em] uppercase text-rose-400">
              Integrity Violation Detected
            </h2>
            <p className="text-slate-400 text-sm tracking-widest uppercase">
              Focus Lost - Event Logged
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-full border border-rose-500/30 bg-rose-950/40 px-5 py-2 text-xs font-mono text-rose-300 shadow-inner">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-rose-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-rose-500" />
            </span>
            INTEGRITY_FLAG transmitted to Operator Plane
          </div>
        </div>
      )}

      <header className="flex h-16 shrink-0 items-center justify-between border-b border-white/10 bg-slate-950/60 backdrop-blur-md px-6">
        <div className="flex items-center gap-4">
          <div className="flex h-8 w-8 items-center justify-center rounded border border-cyan-500/30 bg-cyan-500/10 text-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.15)]">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <div>
            <h1 className="font-bold text-slate-100 tracking-wide text-sm">
              ZT-ATE workspace
            </h1>
            <p className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold">
              {candidateRole}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-xs font-semibold text-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.1)]">
          <Lock className="h-3.5 w-3.5" />
          <span className="uppercase tracking-wider">End-to-End Encrypted</span>
          <span className="relative flex h-2 w-2 ml-1">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
          </span>
        </div>

        <div className="flex items-center gap-6">
          <div className="flex flex-col items-end">
            <span className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold">
              Cryptographic ID
            </span>
            <span className="font-mono text-xs text-slate-300">
              {cryptoPrefix}********
            </span>
          </div>
          <CountdownTimer onExpire={handleTimerExpire} paused={timerPaused} />
        </div>
      </header>

      <main className="flex-1 overflow-hidden p-4">
        <div className="grid h-full grid-cols-12 gap-4">
          <div className="col-span-4 flex flex-col gap-4">
            <div className="min-h-0 flex-1 overflow-hidden rounded-xl border border-white/10 bg-white/5 backdrop-blur-md flex flex-col shadow-2xl">
              <div className="flex items-center gap-2 border-b border-white/10 bg-black/40 px-4 py-3">
                <ClipboardList className="h-4 w-4 text-cyan-400" />
                <h2 className="text-[11px] font-bold uppercase tracking-widest text-slate-300">
                  Scenario Objective
                </h2>
              </div>
              <div className="flex-1 overflow-y-auto p-5 text-sm leading-relaxed text-slate-300 [scrollbar-width:thin] [scrollbar-color:#334155_transparent]">
                <p className="mb-4 text-white font-semibold text-base">
                  Implement Zero-Trust API Boundary
                </p>
                <p className="mb-5 text-slate-400 text-[13px]">
                  Your objective is to design a secure API route that mitigates
                  SSRF vulnerabilities while enforcing strict Role-Based Access
                  Control (RBAC). The environment requires deterministic
                  responses and absolute segregation of biometric overlays
                  depending on the requesting plane.
                </p>
                <div className="space-y-3 text-[13px] text-slate-300">
                  <div className="flex items-start gap-3 bg-black/20 p-3 rounded-lg border border-white/5">
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-cyan-500 mt-0.5" />
                    <span>
                      Validate all ingress payloads using strict schema parsing
                      (Zod).
                    </span>
                  </div>
                  <div className="flex items-start gap-3 bg-black/20 p-3 rounded-lg border border-white/5">
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-cyan-500 mt-0.5" />
                    <span>
                      Ensure cryptographic isolation between Candidate and
                      Operator planes.
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div className="h-36 shrink-0">
              <BiometricSentinel
                sessionId={sessionId}
                isCompiling={isCompiling}
              />
            </div>

            <div className="flex h-[28%] shrink-0 flex-col overflow-hidden rounded-xl border border-cyan-500/30 bg-white/5 backdrop-blur-md shadow-[0_0_30px_rgba(34,211,238,0.05)]">
              <div className="flex items-center justify-between border-b border-cyan-500/30 bg-cyan-950/20 px-4 py-3">
                <div className="flex items-center gap-2">
                  <Cpu className="h-4 w-4 text-cyan-400" />
                  <h2 className="text-[11px] font-bold uppercase tracking-widest text-cyan-200">
                    Live-Sync Supervisor
                  </h2>
                </div>
                <Activity className="h-4 w-4 text-cyan-400 animate-pulse" />
              </div>

              <div className="flex flex-1 flex-col items-center justify-center relative bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-cyan-900/20 via-transparent to-transparent p-5">
                <div className="relative mb-6 flex h-16 w-16 items-center justify-center">
                  <div className="absolute h-full w-full animate-ping rounded-full bg-cyan-400/20 duration-1000" />
                  <div className="absolute h-12 w-12 animate-pulse rounded-full bg-cyan-400/40 blur-[4px] duration-700" />
                  <div className="relative h-6 w-6 rounded-full bg-cyan-400 shadow-[0_0_20px_rgba(34,211,238,1)]" />
                </div>

                <div className="w-full space-y-3 overflow-y-auto [scrollbar-width:none]">
                  <div className="flex gap-3 items-start">
                    <span className="text-[10px] font-mono text-slate-500 font-bold uppercase shrink-0 pt-0.5">
                      [SYSTEM]
                    </span>
                    <p className="text-[13px] text-slate-300">
                      Environment synchronized. Awaiting approach breakdown.
                    </p>
                  </div>
                  <div className="flex gap-3 items-start">
                    <span className="text-[10px] font-mono text-cyan-400 font-bold uppercase shrink-0 pt-0.5">
                      [CANDIDATE]
                    </span>
                    <p className="text-[13px] text-white font-medium">
                      I will start by defining the Zod schema for input
                      validation to protect against SSRF injection...
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="col-span-8 flex flex-col gap-4">
            <SandboxPane isLocked={sandboxLocked} />

            <div className="h-[25%] shrink-0 flex flex-col overflow-hidden rounded-xl border border-white/10 bg-[#0d1117] shadow-2xl">
              <div className="flex items-center gap-2 border-b border-white/10 bg-black/40 px-4 py-2 shrink-0">
                <Terminal className="h-4 w-4 text-slate-400" />
                <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
                  Runtime Output Console
                </span>
              </div>
              <div className="flex-1 overflow-y-auto p-4 font-mono text-[12px] [scrollbar-width:thin] [scrollbar-color:#334155_transparent]">
                <div className="flex gap-3 text-slate-400 mb-1.5">
                  <span className="shrink-0">19:01:24.032</span>
                  <span>Initiating compilation pipeline...</span>
                </div>
                <div className="flex gap-3 text-emerald-400 mb-1.5">
                  <span className="shrink-0 text-slate-500">19:01:25.105</span>
                  <span>Syntax check passed.</span>
                </div>
                <div className="flex gap-3 text-emerald-400 mb-1.5">
                  <span className="shrink-0 text-slate-500">19:01:25.210</span>
                  <span>Type verification successful.</span>
                </div>
                <div className="flex gap-3 text-rose-500 mb-1.5">
                  <span className="shrink-0 text-rose-500/70">
                    19:01:26.402
                  </span>
                  <span className="font-bold">
                    [ERROR] Deterministic contract violation:
                  </span>
                </div>
                <div className="flex gap-3 text-rose-400 mb-3">
                  <span className="shrink-0 opacity-0">19:01:26.402</span>
                  <span>
                    Expected strict RBAC check for X-ZT-Plane header. None
                    found in route.ts logic block.
                  </span>
                </div>
                <div className="flex gap-2 text-slate-400 mt-2 items-center">
                  <span className="text-cyan-400 font-bold">
                    candidate@zt-ate
                  </span>
                  :<span className="text-blue-400">~/workspace</span>${" "}
                  <span className="animate-pulse w-2 h-4 bg-slate-400 inline-block ml-1" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
