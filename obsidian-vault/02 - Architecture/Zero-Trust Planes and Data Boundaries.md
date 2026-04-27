# Zero-Trust Planes and Data Boundaries

## Plane Enforcement
| Concern | Current Control |
|---------|-----------------|
| Plane identity | Signed JWT role claim: `https://zt-ate.com/roles` |
| Candidate session binding | Signed JWT session claim: `https://zt-ate.com/session_id` |
| Operator access | `require_operator` FastAPI dependency |
| Candidate snapshot | `/api/sessions/{id}/candidate` plus `sanitize_for_candidate()` |
| CORS | Explicit localhost/Tauri origin whitelist |
| Scoring contamination | `TechnicalScoringInput` rejects biometric keys |

## Candidate Plane Policy
- Must never receive raw biometric telemetry.
- Must never receive `operator_review_flags`, `review_segments`, or `stress_markers`.
- Must call `/api/sessions/{id}/candidate`, not the full operator snapshot endpoint.
- Candidate JWTs are bound to one session ID.
- BiometricSentinel sends telemetry outbound only through
  `POST /api/sessions/{id}/events`.

## Operator Plane Policy
- Receives full `InterviewSessionSnapshot` including `TelemetryOverlayPlane`.
- Must authenticate with an operator JWT.
- Owns review, adjudication, finalization, audit export, and report access.
- Glass-box reports are operator artifacts; only explicitly candidate-safe
  summaries may cross into candidate-facing views.

## EEOC Compliance Firewall
Three-layer structural enforcement:

1. `live_interface.py`: coaching context is driven by technical state, not overlay state.
2. `genai_config.py`: live model instruction forbids biometric awareness.
3. `contracts.py`: `TechnicalScoringInput` rejects biometric fields before scoring.

## Candidate Sanitizer
`sanitize_for_candidate()` deep-copies the session snapshot and zeroes:

- overlay enabled state
- collection mode
- telemetry timeline
- stress markers
- overlay segments
- operator review flags
- review segments
- latest stress index
- latest heart rate
- processing lag

It also forces `excluded_from_automated_scoring=true`.

## JWT Claim Structure
```json
{
  "iss": "zt-ate-backend",
  "sub": "operator|<session_id>",
  "aud": "zt-ate-core",
  "iat": 1234567890,
  "exp": 1234567890,
  "jti": "<uuid4>",
  "https://zt-ate.com/roles": ["operator"],
  "https://zt-ate.com/session_id": "<session_id>"
}
```

## Linked Notes
- [[03 - Workstreams/Session API and Contracts]]
- [[02 - Architecture/JWT Auth and Security Model]]
- [[05 - Decisions/ADR-0002 JWT Auth Strategy]]
- [[05 - Decisions/ADR-0004 Tauri 2 Desktop Conversion]]
