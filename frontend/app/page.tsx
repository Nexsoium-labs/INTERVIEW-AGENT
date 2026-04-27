export default function HomePage() {
  return (
    <main className="shell">
      <section className="hero">
        <span className="caption">ZT-ATE Frontend</span>
        <h1>Dual-plane interview console with hard scoring isolation.</h1>
        <p>
          The backend now exposes separate technical scoring and telemetry overlay APIs. Use the
          dedicated routes below to open the operator console or the candidate-safe session view.
        </p>
        <div className="nav-links">
          <a className="nav-link" href="/operator/?session=demo-session-777">
            Open operator console
          </a>
          <a className="nav-link" href="/candidate/?session=demo-session-777">
            Open candidate view
          </a>
        </div>
      </section>

      <section className="grid three">
        <article className="card">
          <h3>Technical Plane</h3>
          <p>Locked verdict, rubric scores, artifacts, and replayable milestones.</p>
        </article>
        <article className="card">
          <h3>Overlay Plane</h3>
          <p>Operator-only telemetry timeline, review markers, and stress correlation segments.</p>
        </article>
        <article className="card">
          <h3>Governance</h3>
          <p>Consent capture, audit export, glass-box reporting, and human signoff remain mandatory.</p>
        </article>
      </section>
    </main>
  );
}
