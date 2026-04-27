# Dev Mode Session Testing

## Objective
Exercise candidate and operator UIs against the local FastAPI backend using the
same direct API path used by the Tauri desktop build.

## Preconditions
- Backend running on `http://127.0.0.1:8000`.
- Frontend running on `http://localhost:3000`.
- Operator token stored in `localStorage("zt_operator_token")`.
- Candidate token stored in `localStorage("zt_candidate_token")`.

## Start Backend
```powershell
cd "C:\Users\BHARATH ANTONY\Documents\AI AGENT\INTERVIEW AGENT\backend"
$env:ENFORCE_SECRET_SCAN="false"
.\.venv\Scripts\python.exe run.py
```

Health check:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/health
```

## Start Frontend
```powershell
cd "C:\Users\BHARATH ANTONY\Documents\AI AGENT\INTERVIEW AGENT\frontend"
npm run dev
```

## Test Routes
| View | URL |
|------|-----|
| Candidate workspace | `http://localhost:3000/candidate?session=<session_id>` |
| Operator console | `http://localhost:3000/operator?session=<session_id>` |
| First-run setup | `http://localhost:3000/setup` |

## Token Flow
Mint an operator token:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/auth/issue-token" `
  -ContentType "application/json" `
  -Body '{"operator_secret":"<OPERATOR_MASTER_SECRET>"}'
```

Create a session with the operator token:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/sessions" `
  -Headers @{ Authorization = "Bearer <operator_token>" } `
  -ContentType "application/json" `
  -Body '{"candidate_id":"test_001","candidate_role":"Senior Engineer","scenario_id":"kubernetes_outage_recovery"}'
```

Store returned tokens in browser localStorage:

```javascript
localStorage.setItem("zt_operator_token", "<operator_token>")
localStorage.setItem("zt_candidate_token", "<candidate_token>")
```

## Candidate Validation
- [ ] Page loads at `/candidate?session=<session_id>`.
- [ ] Candidate call hits `/api/sessions/{id}/candidate`.
- [ ] Overlay fields are zeroed in the network response.
- [ ] CountdownTimer runs.
- [ ] SandboxPane tabs switch.
- [ ] BiometricSentinel asks for camera permission.
- [ ] Telemetry posts to `/api/sessions/{id}/events`.
- [ ] Camera denial does not crash the page.

## Operator Validation
- [ ] Page loads at `/operator?session=<session_id>`.
- [ ] Operator call hits `/api/sessions/{id}`.
- [ ] Full telemetry overlay is visible when present.
- [ ] Technical Plane and Task Outcomes render.
- [ ] Pulse/Stress SVG chart renders.
- [ ] Page remains viewport locked.

## Security Regression Checks
- [ ] Candidate token for a different session returns HTTP 403.
- [ ] Missing token returns HTTP 401 or 403.
- [ ] Candidate route never calls `/api/sessions/{id}`.
- [ ] Operator-only routes reject candidate JWTs.

## Linked Notes
- [[05 - Decisions/ADR-0002 JWT Auth Strategy]]
- [[05 - Decisions/ADR-0004 Tauri 2 Desktop Conversion]]
- [[03 - Workstreams/Session API and Contracts]]
