import { GlassBoxReport, InterviewMilestoneSnapshot, InterviewSessionSnapshot } from "@/lib/types";

function toneForRecommendation(recommendation: string | null | undefined) {
  if (recommendation === "advance") return "chip good";
  if (recommendation === "hold") return "chip warn";
  return "chip risk";
}

export function OperatorConsole({
  session,
  report,
  milestones
}: {
  session: InterviewSessionSnapshot;
  report: GlassBoxReport | null;
  milestones: InterviewMilestoneSnapshot[];
}) {
  const verdict = session.technical.technical_verdict;

  return (
    <main className="shell">
      <section className="hero">
        <span className="caption">Operator Console</span>
        <h1>Technical verdict locked apart from the telemetry overlay.</h1>
        <p>
          The operator sees both planes at once, but the automated verdict is sourced only from
          evidence artifacts and rubric outputs. Overlay signals stay visible for review and audit.
        </p>
        <div className="chip-row">
          <span className="chip">{session.session_status}</span>
          <span className="chip">{session.scenario_id}</span>
          <span className={toneForRecommendation(verdict?.recommendation)}>
            {verdict?.recommendation ?? "pending"}
          </span>
        </div>
      </section>

      <section className="grid three">
        <article className="card metric">
          <span className="caption">Locked Technical Score</span>
          <strong>{session.technical.technical_score.toFixed(2)}</strong>
          <p>Objective scoring from commands, diff, hidden tests, health checks, sandbox stream, and final state.</p>
        </article>
        <article className="card metric">
          <span className="caption">Overlay Review Segments</span>
          <strong>{session.overlay.review_segments.length}</strong>
          <p>Operator-only attention markers correlated to simulation milestones.</p>
        </article>
        <article className="card metric">
          <span className="caption">Milestones</span>
          <strong>{milestones.length}</strong>
          <p>Replayable checkpoints for audit reconstruction and verdict reproducibility.</p>
        </article>
      </section>

      <section className="grid two">
        <article className="card">
          <h3>Technical Rubric</h3>
          <div className="list">
            {session.technical.rubric_scores.map((rubric) => (
              <div key={rubric.rubric_id} className="list-item">
                <strong>
                  {rubric.label}: {rubric.score.toFixed(2)} / {rubric.max_score.toFixed(2)}
                </strong>
                <p>{rubric.rationale}</p>
              </div>
            ))}
          </div>
        </article>

        <article className="card">
          <h3>Telemetry Overlay Timeline</h3>
          <div className="timeline" aria-label="Overlay timeline">
            {(session.overlay.telemetry_timeline.length
              ? session.overlay.telemetry_timeline
              : [{ point_id: "empty", stress_index: 0.08 } as const]
            ).map((point, index) => (
              <div
                key={`${point.point_id}-${index}`}
                className="timeline-bar"
                style={{ height: `${Math.max(16, ((point.stress_index ?? 0.08) + 0.1) * 120)}px` }}
                title={`Stress ${(point.stress_index ?? 0).toFixed(2)}`}
              />
            ))}
          </div>
          <p>
            Overlay excluded from automated scoring:{" "}
            <strong>{session.overlay.excluded_from_automated_scoring ? "yes" : "no"}</strong>
          </p>
        </article>
      </section>

      <section className="grid two">
        <article className="card">
          <h3>Evidence Bundle</h3>
          <div className="list">
            {session.technical.evidence_bundle.map((artifact) => (
              <div key={artifact.artifact_id} className="list-item">
                <strong>{artifact.label}</strong>
                <p>{artifact.content.slice(0, 220)}</p>
              </div>
            ))}
          </div>
        </article>

        <article className="card">
          <h3>Review Segments</h3>
          <div className="list">
            {session.overlay.review_segments.length ? (
              session.overlay.review_segments.map((segment) => (
                <div key={segment.segment_id} className="list-item">
                  <strong>{segment.priority.toUpperCase()} priority</strong>
                  <p>{segment.review_rationale}</p>
                </div>
              ))
            ) : (
              <div className="list-item">
                <strong>No operator review segment yet</strong>
                <p>The overlay channel is available, but nothing has crossed the review threshold.</p>
              </div>
            )}
          </div>
        </article>
      </section>

      <section className="grid two">
        <article className="card">
          <h3>Replay Milestones</h3>
          <div className="list">
            {milestones.map((milestone) => (
              <div key={milestone.milestone_id} className="list-item">
                <strong>{milestone.stage}</strong>
                <p>{milestone.note}</p>
              </div>
            ))}
          </div>
        </article>

        <article className="card">
          <h3>Human Signoff</h3>
          <p>{report?.explicit_biometric_exclusion_statement ?? "Finalize the interview to generate the glass-box report."}</p>
          <div className="chip-row">
            <span className="chip">{session.human_decision ?? "pending"}</span>
            <span className="chip">
              {report ? (report.human_approval_required ? "approval required" : "approved") : "not finalized"}
            </span>
          </div>
        </article>
      </section>
    </main>
  );
}
