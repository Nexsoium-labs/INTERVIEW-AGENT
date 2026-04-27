# Biometric Sentinel

## File
`frontend/app/(interview)/candidate/_components/BiometricSentinel.tsx`

## Purpose
WebRTC rPPG biometric extraction component in the candidate workspace. It reads
local webcam frames, derives aggregate pulse/RGB telemetry, and posts bounded
numeric signals to the local FastAPI sidecar.

## Architecture
```text
getUserMedia(video)
  -> muted local video element
  -> requestAnimationFrame canvas sampling
  -> RGB signal extraction from forehead region
  -> 500ms BPM sampler
  -> 5000ms telemetry flush
  -> POST http://127.0.0.1:8000/api/sessions/{id}/events
```

No raw video leaves the browser.

## Telemetry Payload
`frontend/lib/api.ts` wraps the direct backend call through `ingestTelemetry()`.

Payload shape:

```json
{
  "event_type": "webcam_frame",
  "telemetry": {
    "heart_rate_bpm": 80,
    "rppg_confidence": 0.75,
    "silence_ms": 0
  },
  "raw_payload": {
    "rgb_variance": {"r": 0, "g": 0, "b": 0, "sigma": 0},
    "source": "rppg_sentinel_v1",
    "timestamp_utc": "..."
  }
}
```

## Permission State Machine
```text
prompt -> requesting -> granted
                    -> denied
                    -> error
```

Denied and error states render a technical-only fallback card and do not block
the interview.

## Token Resolution
1. `token` prop
2. `localStorage("zt_candidate_token")`
3. `null` in dev fallback paths

## EEOC Boundary
- Telemetry enters only the backend overlay plane.
- Technical scoring rejects biometric fields.
- Candidate session snapshots are returned through
  `/api/sessions/{id}/candidate`, which strips overlay fields server-side.
- Operator views can inspect overlay data but must use an operator JWT.

## Current Status
- [x] Webcam capture and local frame sampling.
- [x] Direct sidecar telemetry ingest.
- [x] Graceful camera-denied mode.
- [x] Candidate-safe read path separated from operator read path.

## V2 Roadmap
1. Replace simulated BPM with real rPPG processing through WASM/WebGPU.
2. Bind `isCompiling` to actual sandbox compile callbacks.
3. Add consent-aware telemetry controls in candidate setup.

## Linked Notes
- [[03 - Workstreams/Candidate Plane UI]]
- [[02 - Architecture/Zero-Trust Planes and Data Boundaries]]
- [[03 - Workstreams/Session API and Contracts]]
