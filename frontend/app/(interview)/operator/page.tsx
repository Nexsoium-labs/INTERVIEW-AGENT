"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  Brain,
  ChartSpline,
  ClipboardCheck,
  Gauge,
  Shield
} from "lucide-react";

import { getSession } from "@/lib/api";
import type { InterviewSessionSnapshot } from "@/lib/types";

function OperatorSessionInner() {
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session");
  const [sessionData, setSessionData] = useState<InterviewSessionSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!sessionId) {
      setError("No session ID. Provide ?session=<uuid>.");
      setLoading(false);
      return;
    }

    const token =
      typeof window !== "undefined" ? localStorage.getItem("zt_operator_token") : null;
    if (!token) {
      setError("Operator token not found. Authenticate first.");
      setLoading(false);
      return;
    }

    getSession(sessionId, token)
      .then(setSessionData)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "Failed to load session.")
      )
      .finally(() => setLoading(false));
  }, [sessionId]);

  if (loading) {
    return (
      <div className="h-screen w-full flex items-center justify-center bg-slate-950">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
          <p className="text-sm uppercase tracking-widest text-slate-400">
            Loading Telemetry Board
          </p>
        </div>
      </div>
    );
  }

  if (error || !sessionData) {
    return (
      <div className="h-screen w-full flex items-center justify-center bg-slate-950">
        <div className="max-w-md text-center space-y-3 px-6">
          <p className="text-xs uppercase tracking-widest text-rose-400">Operator Error</p>
          <p className="text-sm text-slate-300">{error ?? "Session not found."}</p>
        </div>
      </div>
    );
  }

  const taskOutcomes = sessionData.technical.task_outcomes;
  const failedActionCount = taskOutcomes.reduce(
    (sum, task) => sum + task.failed_action_count,
    0
  );
  const syntaxErrorRate =
    Math.round((failedActionCount / Math.max(sessionData.event_count, 1)) * 1000) /
    10;
  const inFlightTask =
    taskOutcomes.find((task) => task.status === "partial") ?? taskOutcomes[0];

  const telemetryTimeline = [...sessionData.overlay.telemetry_timeline].sort(
    (a, b) =>
      new Date(a.timestamp_utc).getTime() - new Date(b.timestamp_utc).getTime()
  );
  const latestTelemetry = telemetryTimeline[telemetryTimeline.length - 1];

  const stressPolyline = telemetryTimeline
    .map((point, index) => {
      const denominator = Math.max(telemetryTimeline.length - 1, 1);
      const x = (index / denominator) * 100;
      const stress = point.stress_index ?? 0;
      const y = (1 - stress) * 100;
      return `${x},${y}`;
    })
    .join(" ");

  const pulsePolyline = telemetryTimeline
    .map((point, index) => {
      const denominator = Math.max(telemetryTimeline.length - 1, 1);
      const x = (index / denominator) * 100;
      const bpm = point.heart_rate_bpm ?? 60;
      const bpmNormalized = Math.min(Math.max((bpm - 60) / 80, 0), 1);
      const y = (1 - bpmNormalized) * 100;
      return `${x},${y}`;
    })
    .join(" ");

  const flaggedMarkers = [
    ...sessionData.overlay.operator_review_flags,
    ...sessionData.overlay.stress_markers.map(
      (marker) =>
        `${new Date(marker.start_timestamp_utc).toISOString().slice(11, 16)} UTC - ${
          marker.rationale
        }`
    )
  ];

  return (
    <div className="h-screen bg-slate-950 text-slate-100 flex flex-col overflow-hidden">
      <div className="flex flex-col flex-1 overflow-hidden w-full max-w-[1440px] mx-auto px-4 sm:px-8 py-6">
        <header className="mb-5 flex flex-wrap items-start justify-between gap-4 border-b border-slate-800 pb-5 shrink-0">
          <div className="space-y-1">
            <p className="text-xs uppercase tracking-[0.18em] text-cyan-300/75">
              Operator Console
            </p>
            <h1 className="text-2xl font-semibold text-white">
              Executive Interview Telemetry Board
            </h1>
            <p className="text-sm text-slate-400">
              Session {sessionData.session_id} - {sessionData.candidate_role}
            </p>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-cyan-200">
            <Shield className="h-4 w-4" />
            Plane Operator
          </div>
        </header>

        <main className="flex-1 overflow-hidden grid gap-6 xl:grid-cols-2">
          <section className="space-y-5 overflow-y-auto [scrollbar-width:thin] [scrollbar-color:#334155_transparent] pr-1">
            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-2xl shadow-black/30">
              <h2 className="mb-4 flex items-center gap-2 text-base font-semibold text-white">
                <Gauge className="h-5 w-5 text-emerald-300" />
                Technical Plane
              </h2>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-4">
                  <p className="text-xs uppercase tracking-[0.12em] text-slate-500">Score</p>
                  <p className="mt-1 text-3xl font-semibold text-emerald-300">
                    {sessionData.technical.technical_score}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-4">
                  <p className="text-xs uppercase tracking-[0.12em] text-slate-500">
                    Task Status
                  </p>
                  <p className="mt-1 text-sm font-medium text-slate-100">
                    {inFlightTask?.title ?? "No active task"}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-4">
                  <p className="text-xs uppercase tracking-[0.12em] text-slate-500">
                    Syntax Error Rate
                  </p>
                  <p className="mt-1 text-3xl font-semibold text-amber-300">
                    {syntaxErrorRate}%
                  </p>
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-2xl shadow-black/30">
              <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.15em] text-slate-300">
                <ClipboardCheck className="h-4 w-4 text-cyan-300" />
                Current Task Outcomes
              </h3>
              <div className="space-y-3">
                {taskOutcomes.map((task) => (
                  <div
                    key={task.outcome_id}
                    className="rounded-xl border border-slate-800 bg-slate-950/80 p-4"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm font-medium text-white">{task.title}</p>
                      <span className="rounded-full border border-slate-700 bg-slate-900 px-2.5 py-0.5 text-xs uppercase tracking-[0.12em] text-slate-300">
                        {task.status}
                      </span>
                    </div>
                    <p className="mt-2 text-sm text-slate-400">{task.summary}</p>
                    <p className="mt-2 text-xs text-slate-500">
                      Failed Actions: {task.failed_action_count} - Duration:{" "}
                      {Math.round(task.duration_ms / 1000)}s
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="space-y-5 overflow-y-auto [scrollbar-width:thin] [scrollbar-color:#334155_transparent] pr-1">
            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-2xl shadow-black/30">
              <h2 className="mb-4 flex items-center gap-2 text-base font-semibold text-white">
                <Brain className="h-5 w-5 text-fuchsia-300" />
                Telemetry Plane
              </h2>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-4">
                  <p className="text-xs uppercase tracking-[0.12em] text-slate-500">
                    Latest BPM
                  </p>
                  <p className="mt-1 text-2xl font-semibold text-rose-300">
                    {latestTelemetry?.heart_rate_bpm ?? "--"}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-4">
                  <p className="text-xs uppercase tracking-[0.12em] text-slate-500">
                    Stress Index
                  </p>
                  <p className="mt-1 text-2xl font-semibold text-amber-300">
                    {Math.round((latestTelemetry?.stress_index ?? 0) * 100)}%
                  </p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-4">
                  <p className="text-xs uppercase tracking-[0.12em] text-slate-500">
                    Overlay Lag
                  </p>
                  <p className="mt-1 text-2xl font-semibold text-cyan-300">
                    {sessionData.overlay.overlay_processing_lag_ms}ms
                  </p>
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-2xl shadow-black/30">
              <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.15em] text-slate-300">
                <ChartSpline className="h-4 w-4 text-emerald-300" />
                Pulse / Stress Correlation
              </h3>
              <div className="rounded-xl border border-slate-800 bg-slate-950/85 p-4">
                <svg viewBox="0 0 100 100" className="h-44 w-full" aria-label="Pulse stress chart">
                  <defs>
                    <linearGradient id="stressGradient" x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%" stopColor="#f59e0b" />
                      <stop offset="100%" stopColor="#ef4444" />
                    </linearGradient>
                    <linearGradient id="pulseGradient" x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%" stopColor="#22d3ee" />
                      <stop offset="100%" stopColor="#34d399" />
                    </linearGradient>
                  </defs>
                  {[0, 25, 50, 75, 100].map((line) => (
                    <line
                      key={line}
                      x1="0"
                      x2="100"
                      y1={line}
                      y2={line}
                      stroke="#1e293b"
                      strokeWidth="0.4"
                    />
                  ))}
                  <polyline
                    points={stressPolyline}
                    fill="none"
                    stroke="url(#stressGradient)"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                  <polyline
                    points={pulsePolyline}
                    fill="none"
                    stroke="url(#pulseGradient)"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                </svg>
                <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-slate-400">
                  <span className="inline-flex items-center gap-1.5">
                    <Activity className="h-3.5 w-3.5 text-amber-300" />
                    Stress
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <Activity className="h-3.5 w-3.5 text-cyan-300" />
                    Pulse
                  </span>
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-2xl shadow-black/30">
              <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.15em] text-slate-300">
                <AlertTriangle className="h-4 w-4 text-rose-300" />
                Flagged Behavioral Timeline
              </h3>
              <div className="space-y-2">
                {flaggedMarkers.map((marker, index) => (
                  <div
                    key={`${marker}-${index}`}
                    className="rounded-xl border border-slate-800 bg-slate-950/80 p-3 text-sm text-slate-200"
                  >
                    {marker}
                  </div>
                ))}
              </div>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}

export default function OperatorSessionPage() {
  return (
    <Suspense
      fallback={
        <div className="h-screen w-full flex items-center justify-center bg-slate-950">
          <div className="h-8 w-8 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
        </div>
      }
    >
      <OperatorSessionInner />
    </Suspense>
  );
}
