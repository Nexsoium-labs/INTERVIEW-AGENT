"use client";

import { useEffect, useState } from "react";
import { Clock } from "lucide-react";

interface CountdownTimerProps {
  /** Total interview duration in seconds. Defaults to 45 minutes. */
  initialSeconds?: number;
  /** Fired exactly once when the timer reaches 00:00. */
  onExpire?: () => void;
  /**
   * When true, the countdown freezes in place.
   * Used by anti-cheat to pause the timer during an integrity violation.
   */
  paused?: boolean;
}

export function CountdownTimer({
  initialSeconds = 45 * 60,
  onExpire,
  paused = false,
}: CountdownTimerProps) {
  const [secondsLeft, setSecondsLeft] = useState(initialSeconds);

  useEffect(() => {
    if (paused) return;

    const id = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          clearInterval(id);
          onExpire?.();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paused]);

  const minutes = Math.floor(secondsLeft / 60);
  const secs = secondsLeft % 60;
  const display = `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;

  const isCritical = secondsLeft > 0 && secondsLeft <= 5 * 60;
  const isExpired = secondsLeft === 0;

  return (
    <div className="flex items-center gap-2 rounded bg-white/5 px-3 py-1.5 border border-white/10 shadow-inner">
      <Clock
        className={`h-4 w-4 transition-colors duration-500 ${
          isCritical || isExpired ? "text-rose-400" : "text-cyan-400"
        }`}
      />
      <span
        className={`font-mono text-sm font-semibold tracking-wider transition-colors duration-500 ${
          isExpired
            ? "text-rose-600 animate-pulse"
            : isCritical
              ? "text-rose-500 animate-pulse"
              : "text-cyan-400"
        }`}
        aria-live="polite"
        aria-label={`Time remaining: ${display}`}
      >
        {display}
      </span>
    </div>
  );
}
