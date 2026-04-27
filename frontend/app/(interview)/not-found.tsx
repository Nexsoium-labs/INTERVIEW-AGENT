import Link from "next/link";

export default function InterviewNotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-[#0a0e27] text-[#e8eaf6] p-4">
      <div className="max-w-md w-full bg-[#111639] rounded-2xl shadow-2xl border border-[#1a1a3e] p-8 space-y-6 text-center">
        <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-amber-900/30">
          <svg className="h-8 w-8 text-[#ffb800]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
        </div>
        <h2 className="text-2xl font-bold font-poppins text-white">Session Cryptographically Invalid or Expired</h2>
        <p className="text-sm text-[#9fa8da]">
          The requested telemetry plane or candidate session could not be verified. Ensure you have the correct endpoint and active session token.
        </p>
        <Link href="/">
          <div className="mt-6 w-full py-3 px-4 bg-gradient-to-r from-[#00d4ff] to-[#7c4dff] hover:brightness-110 text-white rounded-lg font-medium transition-all shadow-lg hover:shadow-[#00d4ff]/20 cursor-pointer text-center block">
            Return to Operations Center
          </div>
        </Link>
      </div>
    </div>
  );
}
