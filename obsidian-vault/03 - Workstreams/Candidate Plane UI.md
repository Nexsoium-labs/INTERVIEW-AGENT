# Candidate Plane UI

## Route
`frontend/app/(interview)/candidate/page.tsx`

Static route:

```text
/candidate?session=<session_id>
```

## Component Tree
```text
CandidateSessionPage (Client Component)
  -> getCandidateSession(sessionId, token)
  -> InteractiveSession (Client; owns sandboxLocked and isCompiling state)
       -> Header
       -> CountdownTimer
       -> Main Workspace
            -> Scenario Objective
            -> BiometricSentinel
            -> Live-Sync Supervisor
            -> SandboxPane
            -> Runtime Output Console
```

## Data Flow
- `session` query param provides the session ID.
- Candidate token is read from `localStorage("zt_candidate_token")`.
- Session data is fetched directly from the Python sidecar through
  `GET http://127.0.0.1:8000/api/sessions/{id}/candidate`.
- The backend applies `sanitize_for_candidate()` before returning the snapshot.
- Candidate UI must never call the full `/api/sessions/{id}` operator snapshot
  endpoint.

## Key Components
| Component | File | Purpose |
|-----------|------|---------|
| `InteractiveSession` | `_components/InteractiveSession.tsx` | Client state bridge |
| `CountdownTimer` | `_components/CountdownTimer.tsx` | Countdown and expiry signal |
| `SandboxPane` | `_components/SandboxPane.tsx` | Code editor tabs with lock overlay |
| `BiometricSentinel` | `_components/BiometricSentinel.tsx` | WebRTC rPPG sensor |

## BiometricSentinel Integration
- Raw webcam video never leaves the browser.
- Aggregate telemetry is posted directly to
  `POST /api/sessions/{id}/events`.
- Telemetry failures are swallowed so the interview workflow does not block.
- Camera denial degrades to a technical-only state.
- Backend contracts keep telemetry in the operator overlay plane and exclude it
  from automated technical scoring.

## Current Status
- [x] Static-export compatible client route.
- [x] Query-param session loading.
- [x] Direct backend sidecar API client.
- [x] Candidate-safe snapshot endpoint.
- [x] WebRTC rPPG telemetry direct ingest.
- [x] Viewport locked to app frame.
- [x] Anti-cheat focus-loss integrity overlay.
- [x] Tauri kiosk window mode.

## Next Actions
1. Add first-class candidate token provisioning UX.
2. Bind compile events to real sandbox execution callbacks.
3. Replace hardcoded objective copy with scenario data from the session.
4. Wire live conversation UI to `/api/sessions/{id}/live-response`.

## Linked Notes
- [[03 - Workstreams/Biometric Sentinel]]
- [[02 - Architecture/Zero-Trust Planes and Data Boundaries]]
- [[03 - Workstreams/Session API and Contracts]]
