# ADR-0002: JWT Auth Strategy

## Status
Accepted (Option A implemented; Option B path reserved)

## Context
The original `X-ZT-Plane` header was client-controllable — any actor could send `X-ZT-Plane: Operator` and receive full biometric telemetry. This was Critical finding C-02 in the Red Team audit.

## Options Evaluated

### Option A — Internal FastAPI JWT Issuance (Chosen)
- Backend mints its own JWTs via `POST /auth/issue-token`
- Algorithm: HS256 with `JWT_SECRET_KEY` (min 32 bytes entropy)
- OIDC-mimic claim structure for future IdP migration
- Pros: zero external dependencies, fast to ship
- Cons: symmetric key (needs rotation strategy)

### Option B — External IdP (JWKS/RS256)
- Replace `_decode()` with JWKS endpoint call to Okta/Auth0/Cognito
- Algorithm: RS256 asymmetric
- Migration path preserved in `auth.py` `_decode()` docstring
- Pros: production-grade, no key rotation burden
- Cons: external dependency, not needed for MVP

## Decision
Implement Option A immediately. Reserve Option B via commented `jwks_uri` path in `config.py` and `auth.py`.

## Implementation
- File: `backend/app/security/auth.py`
- `mint_operator_token()` → 8h TTL, roles=["operator"]
- `mint_candidate_token(session_id)` → 2h TTL, roles=["candidate"]
- `verify_token` FastAPI dependency → validates signature + expiry + audience
- `require_operator` FastAPI dependency → additionally checks roles claim
- Timing attack prevention: `hmac.compare_digest` in `/auth/issue-token`
- Replay attack prevention: `jti` (UUID4) in every token

## Claim Namespace
```
https://zt-ate.com/roles       → ["operator"] or ["candidate"]
https://zt-ate.com/session_id  → session UUID or null
```
OIDC-compliant custom claim namespacing (avoids collision with standard claims).

## Consequences
- All 16+ `X-ZT-Plane` route checks replaced by cryptographic JWT validation
- Operator route protection is now server-enforced, not header-trust-based
- WebSocket auth via `?token=` query param (header not supported in WS upgrade)

## Linked Notes
- [[02 - Architecture/JWT Auth and Security Model]]
- [[02 - Architecture/Zero-Trust Planes and Data Boundaries]]
