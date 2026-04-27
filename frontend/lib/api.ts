import type {
  GlassBoxReport,
  InterviewMilestoneSnapshot,
  InterviewSessionSnapshot,
  TelemetryOverlayPlane
} from "@/lib/types";
import { getApiBaseUrl } from "@/lib/platform";

export const BACKEND_BASE = getApiBaseUrl();
const API_BASE = `${BACKEND_BASE}/api`;

async function fetchJson<T>(
  path: string,
  init?: RequestInit & { token?: string | null }
): Promise<T> {
  const { token, ...rest } = init ?? {};
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((rest.headers as Record<string, string> | undefined) ?? {})
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers,
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }

  return (await response.json()) as T;
}

export async function getSession(
  sessionId: string,
  token: string
): Promise<InterviewSessionSnapshot> {
  return fetchJson<InterviewSessionSnapshot>(`/sessions/${sessionId}`, { token });
}

export async function getOverlay(
  sessionId: string,
  token: string
): Promise<TelemetryOverlayPlane> {
  return fetchJson<TelemetryOverlayPlane>(`/sessions/${sessionId}/overlay`, { token });
}

export async function getMilestones(
  sessionId: string,
  token: string
): Promise<InterviewMilestoneSnapshot[]> {
  return fetchJson<InterviewMilestoneSnapshot[]>(`/sessions/${sessionId}/milestones`, {
    token
  });
}

export async function getReport(sessionId: string, token: string): Promise<GlassBoxReport | null> {
  try {
    return await fetchJson<GlassBoxReport>(`/sessions/${sessionId}/glass-box`, { token });
  } catch {
    return null;
  }
}

export async function getCandidateSession(
  sessionId: string,
  token: string | null
): Promise<InterviewSessionSnapshot> {
  return fetchJson<InterviewSessionSnapshot>(`/sessions/${sessionId}/candidate`, { token });
}

export async function ingestTelemetry(
  sessionId: string,
  payload: {
    event_type: string;
    telemetry: {
      heart_rate_bpm?: number | null;
      rppg_confidence?: number | null;
      silence_ms?: number;
    };
    raw_payload: Record<string, unknown>;
  },
  token: string | null
): Promise<void> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  try {
    await fetch(`${API_BASE}/sessions/${encodeURIComponent(sessionId)}/events`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      keepalive: true,
      signal: AbortSignal.timeout(4_000)
    });
  } catch {
    // Telemetry failure must never block the candidate workflow.
  }
}
