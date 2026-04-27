# JWT Auth and Security Model

## Implementation
- File: `backend/app/security/auth.py`
- Library: `PyJWT[cryptography]>=2.9.0`
- Algorithm: HS256 (symmetric)
- Migration path: Option B (RS256/JWKS from external IdP) — reserved via `_decode()` docstring

## Token Types
| Type | TTL | Issued by | Claims |
|------|-----|-----------|--------|
| Operator | 8 hours | `POST /auth/issue-token` | roles=["operator"] |
| Candidate | 2 hours | `POST /sessions` (operator only) | roles=["candidate"], session_id |

## Endpoint: POST /auth/issue-token
- **Public** — no JWT required
- Validates `master_secret` body field against `settings.operator_master_secret`
- Uses `hmac.compare_digest` for constant-time comparison (timing attack prevention)
- Returns `TokenResponse { access_token, token_type="bearer", expires_in }`

## FastAPI Dependencies
```python
verify_token    → any valid JWT (candidate or operator)
require_operator → JWT must have "operator" in https://zt-ate.com/roles
```

## Route Protection Tiers
| Tier | Routes | Dependency |
|------|--------|-----------|
| PUBLIC | `POST /auth/issue-token`, `GET /` | None |
| VERIFIED | `POST /events`, `POST /consent`, `POST /live-response`, WebSocket | `verify_token` |
| OPERATOR_ONLY | `POST /sessions`, `GET /sessions/{id}`, `/overlay`, `/glass-box`, `/review-segments`, `/audit-export`, `/finalize`, `/human-review` | `require_operator` |

## OIDC-Mimic Claim Structure
```python
ROLES_CLAIM   = "https://zt-ate.com/roles"
SESSION_CLAIM = "https://zt-ate.com/session_id"
```
Standard claims: `sub`, `iss="zt-ate"`, `aud="zt-ate-api"`, `iat`, `exp`, `jti` (UUID4 for replay prevention)

## WebSocket Auth
Token passed as `?token=<jwt>` query parameter (Authorization header not supported in WS upgrade).

## Security Hardening Applied (Sprint 1)
- CORS: `allow_origins=["http://localhost:3000"]` — never wildcard
- CORS headers: `Authorization`, `Content-Type`, `X-Request-ID` only
- SQL injection: `_PLANE_TABLE_ALLOWLIST` frozenset before any f-string table name interpolation
- Secrets: `JWT_SECRET_KEY`, `OPERATOR_MASTER_SECRET` via env vars (never hardcoded in prod)

## Environment Variables
```
JWT_SECRET_KEY=<min 32 bytes entropy — generate with: openssl rand -hex 32>
OPERATOR_MASTER_SECRET=<strong secret>
```

## Linked Notes
- [[02 - Architecture/Zero-Trust Planes and Data Boundaries]]
- [[05 - Decisions/ADR-0002 JWT Auth Strategy]]
- [[03 - Workstreams/Session API and Contracts]]
