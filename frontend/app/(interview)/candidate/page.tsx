"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { getCandidateSession } from "@/lib/api";
import type { InterviewSessionSnapshot } from "@/lib/types";

import { InteractiveSession } from "./_components/InteractiveSession";

function CandidateSessionInner() {
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session");
  const [sessionData, setSessionData] = useState<InterviewSessionSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!sessionId) {
      setError("No session ID. Provide ?session=<uuid> in the URL.");
      setLoading(false);
      return;
    }

    const token =
      typeof window !== "undefined" ? localStorage.getItem("zt_candidate_token") : null;
    getCandidateSession(sessionId, token)
      .then(setSessionData)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "Failed to load session.")
      )
      .finally(() => setLoading(false));
  }, [sessionId]);

  if (loading) {
    return (
      <div className="h-screen w-full flex items-center justify-center bg-[#0a0a0a] text-cyan-300">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
          <p className="text-sm uppercase tracking-widest text-slate-400">
            Initializing Workspace
          </p>
        </div>
      </div>
    );
  }

  if (error || !sessionData) {
    return (
      <div className="h-screen w-full flex items-center justify-center bg-[#0a0a0a]">
        <div className="max-w-md text-center space-y-3 px-6">
          <p className="text-xs uppercase tracking-widest text-rose-400">Session Error</p>
          <p className="text-sm text-slate-300">
            {error ?? "Session not found or expired."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="h-screen w-full flex flex-col bg-[#0a0a0a] text-slate-100 overflow-hidden font-sans relative"
      style={{
        backgroundImage: "url(/bg-quantum.png)",
        backgroundSize: "cover",
        backgroundPosition: "center"
      }}
    >
      <div className="absolute inset-0 bg-slate-950/70 backdrop-blur-[4px] z-0 pointer-events-none" />
      <div className="relative z-10 flex flex-col h-full w-full">
        <InteractiveSession
          sessionId={sessionData.session_id}
          candidateRole={sessionData.candidate_role}
        />
      </div>
    </div>
  );
}

export default function CandidateSessionPage() {
  return (
    <Suspense
      fallback={
        <div className="h-screen w-full flex items-center justify-center bg-[#0a0a0a]">
          <div className="h-8 w-8 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
        </div>
      }
    >
      <CandidateSessionInner />
    </Suspense>
  );
}
