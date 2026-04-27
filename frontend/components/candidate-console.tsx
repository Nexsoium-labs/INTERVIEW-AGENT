import { InterviewSessionSnapshot } from "@/lib/types";

export function CandidateConsole({ session }: { session: InterviewSessionSnapshot }) {
  return (
    <main className="shell">
      <section className="hero">
        <span className="caption">Candidate View</span>
        <h1>Simulation workspace with explicit consent and privacy boundaries.</h1>
        <p>
          This surface intentionally hides evaluator internals. The candidate sees the active
          scenario, session stage, and consent posture, but never the operator overlay or technical
          scoring internals.
        </p>
        <div className="chip-row">
          <span className="chip">{session.candidate_role}</span>
          <span className="chip">{session.scenario_id}</span>
          <span className="chip">{session.simulation_status}</span>
        </div>
      </section>

      <section className="grid two">
        <article className="card">
          <h3>Live Interview Loop</h3>
          <p>
            Voice and text interaction remain candidate-safe. Hints can adapt to pacing, but the
            automated technical verdict is computed from task artifacts only.
          </p>
          <div className="chip-row">
            <span className="chip good">voice / text channel</span>
            <span className="chip">task status: {session.session_status}</span>
          </div>
        </article>

        <article className="card">
          <h3>Consent And Privacy</h3>
          <p>
            {session.consent_record
              ? session.consent_record.disclosure_text
              : "Telemetry collection is disabled until explicit consent is recorded."}
          </p>
          <div className="chip-row">
            <span className="chip">
              telemetry: {session.consent_record?.telemetry_collection_allowed ? "enabled" : "disabled"}
            </span>
            <span className="chip">
              biometrics: {session.consent_record?.biometric_processing_allowed ? "enabled" : "disabled"}
            </span>
          </div>
        </article>
      </section>

      <section className="grid two">
        <article className="card">
          <h3>Scenario Workspace</h3>
          <p>
            Current scenario: <strong>{session.scenario_id}</strong>
          </p>
          <p>
            Event count: <strong>{session.event_count}</strong>
          </p>
          <p>
            Last updated: <strong>{new Date(session.last_updated_utc).toLocaleString()}</strong>
          </p>
        </article>

        <article className="card">
          <h3>Outcome Policy</h3>
          <p>
            Human review remains mandatory before any final hiring disposition. Telemetry, when
            enabled, cannot automatically pass or fail the session.
          </p>
          <div className="chip-row">
            <span className="chip warn">human review required</span>
            <span className="chip good">artifact-based scoring</span>
          </div>
        </article>
      </section>
    </main>
  );
}
