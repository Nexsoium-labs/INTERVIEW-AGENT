"use client";

import { useState } from "react";
import { FileCode2, Lock, Play } from "lucide-react";

type TabName = "route.ts" | "schema.ts";

interface SandboxPaneProps {
  /** When true, an overlay is rendered and the code editor is inaccessible. */
  isLocked: boolean;
}

// ---------------------------------------------------------------------------
// Static code content — swapped by the active tab.
// These are illustrative but scenario-accurate for the ZT-ATE interview task.
// ---------------------------------------------------------------------------

function RouteCode() {
  return (
    <>
      <span className="text-pink-400">import</span>{" "}
      {"{ NextRequest, NextResponse }"}{" "}
      <span className="text-pink-400">from</span>{" "}
      <span className="text-emerald-300">"next/server"</span>;{"\n"}
      <span className="text-pink-400">import</span>{" "}
      {"{ z }"}{" "}
      <span className="text-pink-400">from</span>{" "}
      <span className="text-emerald-300">"zod"</span>;{"\n"}
      {"\n"}
      <span className="text-slate-500 italic">
        {"// Strict UUID validation — no freeform IDs allowed"}
      </span>
      {"\n"}
      <span className="text-cyan-400">const</span> SessionIdSchema = z
      .string().uuid();{"\n"}
      {"\n"}
      <span className="text-pink-400">export async function</span>{" "}
      <span className="text-amber-200">GET</span>(request: NextRequest,{" "}
      {"{ params }"}) {"{"}{"\n"}
      {"  "}
      <span className="text-cyan-400">const</span> {"{ sessionId }"} ={" "}
      <span className="text-pink-400">await</span> params;{"\n"}
      {"  "}
      <span className="text-cyan-400">const</span> result =
      SessionIdSchema.safeParse(sessionId);{"\n"}
      {"\n"}
      {"  "}
      <span className="text-pink-400">if</span> (!result.success) {"{"}{"\n"}
      {"    "}
      <span className="text-pink-400">return</span> NextResponse.json({"{"}
      {" "}error:{" "}
      <span className="text-emerald-300">"Invalid ID format"</span> {"}"},{" "}
      {"{"} status:{" "}
      <span className="text-amber-400">400</span> {"}"});{"\n"}
      {"  "}
      {"}"}{"\n"}
      {"\n"}
      {"  "}
      <span className="text-slate-500 italic">{"// TODO: RBAC validation"}</span>
      {"\n"}
      {"}"}
    </>
  );
}

function SchemaCode() {
  return (
    <>
      <span className="text-pink-400">import</span>{" "}
      {"{ z }"}{" "}
      <span className="text-pink-400">from</span>{" "}
      <span className="text-emerald-300">"zod"</span>;{"\n"}
      {"\n"}
      <span className="text-slate-500 italic">
        {"// Cryptographic session identity contract"}
      </span>
      {"\n"}
      <span className="text-cyan-400">export const</span> SessionIdSchema = z{"\n"}
      {"  "}.string(){"\n"}
      {"  "}.uuid(
      <span className="text-emerald-300">"Session ID must be a valid UUID v4."</span>
      );{"\n"}
      {"\n"}
      <span className="text-cyan-400">export const</span> PlaneSchema = z.enum([{"\n"}
      {"  "}
      <span className="text-emerald-300">"Operator"</span>,{" "}
      <span className="text-emerald-300">"Candidate"</span>,{"\n"}
      {"}"});{"\n"}
      {"\n"}
      <span className="text-slate-500 italic">
        {"// Biometric telemetry — strict bounds enforced server-side"}
      </span>
      {"\n"}
      <span className="text-cyan-400">export const</span> TelemetrySchema = z.object({"{"}{"\n"}
      {"  "}heart_rate_bpm: z.number().min(
      <span className="text-amber-400">30</span>).max(
      <span className="text-amber-400">220</span>).nullable(),{"\n"}
      {"  "}stress_index: z.number().min(
      <span className="text-amber-400">0</span>).max(
      <span className="text-amber-400">1</span>).nullable(),{"\n"}
      {"  "}rppg_confidence: z.number().min(
      <span className="text-amber-400">0</span>).max(
      <span className="text-amber-400">1</span>).nullable(),{"\n"}
      {"  "}speech_cadence_wpm: z.number().positive().nullable(),{"\n"}
      {"}"});{"\n"}
      {"\n"}
      <span className="text-cyan-400">export const</span> EventIngestSchema = z.object({"{"}{"\n"}
      {"  "}session_id: SessionIdSchema,{"\n"}
      {"  "}event_type: z.enum([{"\n"}
      {"    "}
      <span className="text-emerald-300">"WEBCAM_FRAME"</span>,{" "}
      <span className="text-emerald-300">"CODE_DELTA"</span>,{"\n"}
      {"    "}
      <span className="text-emerald-300">"SPEECH_TURN"</span>,{" "}
      <span className="text-emerald-300">"SYSTEM_SIGNAL"</span>,{"\n"}
      {"  "}{"]);"}{"\n"}
      {"  "}telemetry: TelemetrySchema,{"\n"}
      {"  "}raw_payload: z.record(z.unknown()),{"\n"}
      {"}"});{"\n"}
    </>
  );
}

const LINE_COUNT = 20;

export function SandboxPane({ isLocked }: SandboxPaneProps) {
  const [activeTab, setActiveTab] = useState<TabName>("route.ts");

  return (
    <div className="flex-1 flex flex-col overflow-hidden rounded-xl border border-white/10 bg-white/5 backdrop-blur-md shadow-2xl relative">
      {/* Lock overlay — rendered on top when timer expires */}
      {isLocked && (
        <div className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-4 rounded-xl bg-black/75 backdrop-blur-sm">
          <Lock className="h-14 w-14 text-rose-400 drop-shadow-[0_0_20px_rgba(244,63,94,0.6)]" />
          <p className="text-rose-400 font-bold text-xl tracking-[0.15em] uppercase">
            Sandbox Locked
          </p>
          <p className="text-slate-400 text-sm">Interview time has expired.</p>
        </div>
      )}

      {/* Tab bar */}
      <div className="flex items-center bg-[#0d1117] border-b border-white/10 shrink-0">
        {(["route.ts", "schema.ts"] as TabName[]).map((tab) => {
          const isActive = activeTab === tab;
          return (
            <button
              key={tab}
              onClick={() => !isLocked && setActiveTab(tab)}
              disabled={isLocked}
              className={`flex items-center gap-2 border-r border-white/10 px-5 py-3 transition-all duration-150 ${
                isActive
                  ? "bg-[#161b22] border-t-2 border-t-cyan-500 relative"
                  : "opacity-50 hover:opacity-90"
              }`}
            >
              <FileCode2
                className={`h-4 w-4 ${isActive ? "text-cyan-400" : "text-slate-400"}`}
              />
              <span
                className={`font-mono text-[13px] ${
                  isActive ? "text-white" : "text-slate-400"
                }`}
              >
                {tab}
              </span>
              {/* Active underline flush with border-b */}
              {isActive && (
                <div className="absolute bottom-[-1px] left-0 w-full h-[1px] bg-[#161b22]" />
              )}
            </button>
          );
        })}

        {/* Compile & Run — right-aligned */}
        <div className="ml-auto px-4">
          <button
            disabled={isLocked}
            className="flex items-center gap-2 rounded bg-cyan-500/10 px-4 py-1.5 border border-cyan-500/30 text-[11px] font-bold tracking-widest text-cyan-400 hover:bg-cyan-500/20 hover:border-cyan-400 transition-all uppercase shadow-[0_0_15px_rgba(34,211,238,0.15)] disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <Play className="h-3.5 w-3.5 fill-current" />
            Compile &amp; Run
          </button>
        </div>
      </div>

      {/* Code area */}
      <div className="flex-1 bg-black/60 flex font-mono text-[13px] overflow-hidden">
        {/* Line numbers */}
        <div className="w-12 shrink-0 bg-[#0d1117]/80 py-4 text-right text-slate-600 pr-3 select-none border-r border-white/5">
          {Array.from({ length: LINE_COUNT }).map((_, i) => (
            <div key={i} className="leading-[1.6]">
              {i + 1}
            </div>
          ))}
        </div>

        {/* Code content — swaps on tab change */}
        <div className="flex-1 p-4 overflow-auto text-slate-300 leading-[1.6] [scrollbar-width:thin] [scrollbar-color:#334155_transparent] whitespace-pre font-medium">
          {activeTab === "route.ts" ? <RouteCode /> : <SchemaCode />}
        </div>
      </div>
    </div>
  );
}
