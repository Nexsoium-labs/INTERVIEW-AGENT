"use client";

import { useEffect } from "react";

export default function InterviewError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log the error to an observability service
    console.error("Zero-Trust Boundary Caught Error:", error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-[#0a0e27] text-[#e8eaf6] p-4">
      <div className="max-w-md w-full bg-[#111639] rounded-2xl shadow-2xl border border-red-900 p-8 space-y-6 text-center">
        <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-red-900/30">
          <svg className="h-8 w-8 text-[#ff3366]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <h2 className="text-2xl font-bold font-poppins text-white">Security Exception</h2>
        <p className="text-sm text-[#9fa8da]">
          A critical error occurred while attempting to establish the secure session tunnel.
        </p>
        <button
          onClick={() => reset()}
          className="w-full py-3 px-4 bg-gradient-to-r from-red-600 to-red-800 hover:from-red-500 hover:to-red-700 text-white rounded-lg font-medium transition-all shadow-lg hover:shadow-red-500/20"
        >
          Re-Initialize Connection
        </button>
      </div>
    </div>
  );
}
