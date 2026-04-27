# Operator Plane Console

## Route
`frontend/app/(interview)/operator/page.tsx`

Static route:

```text
/operator?session=<session_id>
```

## Layout
```text
h-screen overflow-hidden flex flex-col
  -> Header
       -> Operator Console / Executive Interview Telemetry Board
       -> Plane Operator badge
  -> Main grid
       -> Intelligence Pane
            -> Technical Plane card
            -> Current Task Outcomes
       -> Telemetry Pane
            -> Telemetry Plane card
            -> Pulse/Stress Correlation SVG chart
            -> Flagged Behavioral Timeline
```

## Data Flow
- `session` query param provides the session ID.
- Operator token is read from `localStorage("zt_operator_token")`.
- The page calls `GET http://127.0.0.1:8000/api/sessions/{id}` through
  `frontend/lib/api.ts`.
- The operator console intentionally receives the full telemetry overlay.
- This route is static-export compatible and no longer uses a Server Component
  or Next.js BFF proxy.

## Chart Implementation
- `stressPolyline`: maps `telemetry_timeline` to `(x, 1 - stress) * 100`.
- `pulsePolyline`: maps BPM to a normalized 60-140 range.
- Grid lines render at y=0, 25, 50, 75, 100.
- Stress uses amber-to-red gradient; pulse uses cyan-to-emerald gradient.

## Behavioral Timeline
Combines:

1. `overlay.operator_review_flags`
2. `overlay.stress_markers` formatted as `HH:MM UTC - <rationale>`

## Current Status
- [x] Static-export compatible client route.
- [x] Query-param session loading.
- [x] Direct backend sidecar API client.
- [x] Full operator snapshot rendering.
- [x] Independent pane scrolling.
- [x] SVG pulse/stress correlation chart.

## Next Actions
1. Add live WebSocket telemetry updates.
2. Add operator actions for segment pinning and flag editing.
3. Persist flag edits to audited backend events.
4. Add human review decision controls.

## Linked Notes
- [[02 - Architecture/Zero-Trust Planes and Data Boundaries]]
- [[03 - Workstreams/Session API and Contracts]]
- [[03 - Workstreams/Glass-Box Evaluator]]
