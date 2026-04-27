export type SessionStatus =
  | "idle"
  | "active"
  | "review_pending"
  | "approved"
  | "rejected";

export type Recommendation = "advance" | "hold" | "reject";

export interface TechnicalRubricScore {
  rubric_id: string;
  label: string;
  score: number;
  max_score: number;
  rationale: string;
}

export interface TechnicalTaskArtifact {
  artifact_id: string;
  artifact_type: string;
  label: string;
  content: string;
  content_type: string;
  metadata: Record<string, unknown>;
  captured_at_utc: string;
}

export interface TechnicalVerdict {
  recommendation: Recommendation;
  score: number;
  max_score: number;
  normalized_score: number;
  passed: boolean;
  rationale: string;
  locked: boolean;
  locked_at_utc: string;
  contamination_check_passed: boolean;
}

export interface TechnicalScorePlane {
  scenario_id: string;
  technical_score: number;
  technical_verdict: TechnicalVerdict | null;
  task_outcomes: TechnicalTaskOutcome[];
  rubric_scores: TechnicalRubricScore[];
  evidence_bundle: TechnicalTaskArtifact[];
  contamination_check_passed: boolean;
  locked: boolean;
}

export interface TechnicalTaskOutcome {
  outcome_id: string;
  scenario_id: string;
  title: string;
  status: "passed" | "partial" | "failed";
  summary: string;
  duration_ms: number;
  failed_action_count: number;
  regression_impact: number;
  created_at_utc: string;
}

export interface OperatorReviewSegment {
  segment_id: string;
  start_timestamp_utc: string;
  end_timestamp_utc: string;
  correlated_simulation_event: string | null;
  stress_delta: number;
  confidence: number;
  review_rationale: string;
  priority: "low" | "medium" | "high";
}

export interface TelemetryOverlayPoint {
  point_id: string;
  timestamp_utc: string;
  correlated_event_id: string | null;
  stress_index: number | null;
  heart_rate_bpm: number | null;
  speech_cadence_wpm: number | null;
  keystroke_irregularity: number | null;
  confidence: number;
}

export interface TelemetryOverlayPlane {
  overlay_enabled: boolean;
  collection_mode: "disabled" | "active";
  telemetry_timeline: TelemetryOverlayPoint[];
  stress_markers: TelemetryOverlaySegment[];
  overlay_segments: TelemetryOverlaySegment[];
  operator_review_flags: string[];
  review_segments: OperatorReviewSegment[];
  latest_stress_index: number | null;
  latest_heart_rate_bpm: number | null;
  overlay_processing_lag_ms: number;
  excluded_from_automated_scoring: boolean;
}

export interface TelemetryOverlaySegment {
  segment_id: string;
  start_timestamp_utc: string;
  end_timestamp_utc: string;
  correlated_event_id: string | null;
  stress_delta: number;
  confidence: number;
  rationale: string;
}

export interface ConsentRecord {
  session_id: string;
  telemetry_collection_allowed: boolean;
  biometric_processing_allowed: boolean;
  jurisdiction: string;
  disclosure_text: string;
  source: string;
  recorded_by: string;
  recorded_at_utc: string;
}

export interface InterviewMilestoneSnapshot {
  milestone_id: string;
  session_id: string;
  stage: string;
  captured_at_utc: string;
  event_count: number;
  trace_count: number;
  technical_score: number;
  technical_recommendation: Recommendation | null;
  overlay_enabled: boolean;
  overlay_segment_count: number;
  simulation_status: string;
  note: string;
}

export interface TraceEvent {
  trace_id: string;
  session_id: string;
  node: string;
  reasoning_path: string;
  input_contract: string;
  output_contract: string;
  attributes: Record<string, unknown>;
  started_at_utc: string;
  completed_at_utc: string;
  latency_ms: number;
}

export interface InterviewSessionSnapshot {
  session_id: string;
  candidate_id: string;
  candidate_role: string;
  language: string;
  scenario_id: string;
  technical: TechnicalScorePlane;
  overlay: TelemetryOverlayPlane;
  session_status: SessionStatus;
  simulation_status: string;
  event_count: number;
  last_route_target: string | null;
  report_available: boolean;
  human_decision: "approve" | "reject" | null;
  consent_record: ConsentRecord | null;
  completed_at_utc: string | null;
  last_updated_utc: string;
  trace_events: TraceEvent[];
  milestone_count: number;
}

export interface GlassBoxReport {
  session_id: string;
  locked_technical_verdict: TechnicalVerdict;
  technical_rubric_scores: TechnicalRubricScore[];
  technical_task_outcomes: TechnicalTaskOutcome[];
  evidence_references: string[];
  telemetry_overlay_summary: TelemetryOverlaySummary;
  operator_review_segments: OperatorReviewSegment[];
  explicit_biometric_exclusion_statement: string;
  consensus_summary: string;
  reasoning_map: Record<string, unknown>;
  candidate_safe_summary: string;
  trace_count: number;
  human_approval_required: boolean;
  generated_at_utc: string;
}

export interface TelemetryOverlaySummary {
  overlay_enabled: boolean;
  total_points: number;
  total_segments: number;
  total_review_segments: number;
  latest_stress_index: number | null;
  latest_heart_rate_bpm: number | null;
  excluded_from_automated_scoring: boolean;
}
