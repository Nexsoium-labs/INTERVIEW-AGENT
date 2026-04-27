"""
ZT-ATE JWT Authentication Layer
================================
Option A implementation (internal issuance) architected as a direct
precursor to Option B (external JWKS/OIDC provider).

Migration path to Option B:
  1. Replace `_decode()` with a JWKS-fetching variant using
     `jwt.PyJWKClient(jwks_uri)` — the claim contract (ROLES_CLAIM,
     SESSION_CLAIM, aud, iss) stays identical.
  2. Swap `settings.jwt_secret_key` for an RSA public key loaded from JWKS.
  3. Change `_ALGORITHM` from "HS256" to "RS256".
  The FastAPI dependency functions (`verify_token`, `require_operator`)
  do NOT change at all.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import settings
from app.contracts import InterviewSessionSnapshot

# ---------------------------------------------------------------------------
# Constants — OIDC-mimic claim namespace
# ---------------------------------------------------------------------------

_ALGORITHM = "HS256"          # swap to "RS256" for Option B
_AUDIENCE = "zt-ate-core"
_ISSUER = "zt-ate-backend"

ROLES_CLAIM = "https://zt-ate.com/roles"       # custom namespace (OIDC pattern)
SESSION_CLAIM = "https://zt-ate.com/session_id"

_CANDIDATE_TTL = timedelta(hours=2)
_OPERATOR_TTL = timedelta(hours=8)

_REQUIRED_CLAIMS = ["exp", "iat", "sub", "aud", "iss", "jti"]

# FastAPI bearer extractor — auto_error=True returns 401 if header absent
_http_bearer = HTTPBearer(auto_error=True)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int          # seconds


class SessionCreateResponse(BaseModel):
    """
    Returned by POST /sessions.
    Operator receives both the session snapshot and the candidate token
    to hand to the interviewee — eliminating the need for a second round-trip.
    """
    session: InterviewSessionSnapshot
    candidate_token: str
    candidate_token_expires_in: int = int(_CANDIDATE_TTL.total_seconds())


# ---------------------------------------------------------------------------
# Token minting
# ---------------------------------------------------------------------------

def mint_operator_token() -> TokenResponse:
    """
    Mint a signed operator-tier JWT.
    Caller must have already validated OPERATOR_MASTER_SECRET externally.
    """
    now = datetime.now(UTC)
    exp = now + _OPERATOR_TTL
    token = jwt.encode(
        {
            "iss": _ISSUER,
            "sub": "operator",
            "aud": _AUDIENCE,
            "iat": now,
            "exp": exp,
            "jti": str(uuid.uuid4()),
            ROLES_CLAIM: ["operator"],
        },
        settings.jwt_secret_key,
        algorithm=_ALGORITHM,
    )
    return TokenResponse(
        access_token=token,
        expires_in=int(_OPERATOR_TTL.total_seconds()),
    )


def mint_candidate_token(session_id: str) -> str:
    """
    Mint a candidate-tier JWT cryptographically bound to `session_id`.
    Called automatically when a session is created.
    """
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "iss": _ISSUER,
            "sub": session_id,
            "aud": _AUDIENCE,
            "iat": now,
            "exp": now + _CANDIDATE_TTL,
            "jti": str(uuid.uuid4()),
            ROLES_CLAIM: ["candidate"],
            SESSION_CLAIM: session_id,
        },
        settings.jwt_secret_key,
        algorithm=_ALGORITHM,
    )


# ---------------------------------------------------------------------------
# Token decoding (shared internal path)
# ---------------------------------------------------------------------------

def _decode(token: str) -> dict[str, Any]:
    """
    Decode and fully validate a JWT.
    Raises HTTP 401 on any validation failure — never leaks internal detail.

    Option B migration note: replace the body with:
        jwks_client = jwt.PyJWKClient(settings.jwks_uri)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(token, signing_key.key, algorithms=["RS256"], ...)
    """
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[_ALGORITHM],
            audience=_AUDIENCE,
            issuer=_ISSUER,
            options={"require": _REQUIRED_CLAIMS},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ---------------------------------------------------------------------------
# FastAPI dependency graph
# ---------------------------------------------------------------------------

async def verify_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_http_bearer)],
) -> dict[str, Any]:
    """
    Dependency: any valid JWT (operator OR candidate).
    Validates signature, expiry, audience, issuer, and required claims.
    Inject with: claims: Annotated[dict, Depends(verify_token)]
    """
    return _decode(credentials.credentials)


async def require_operator(
    claims: Annotated[dict[str, Any], Depends(verify_token)],
) -> dict[str, Any]:
    """
    Dependency: requires the 'operator' role in the ROLES_CLAIM array.
    Raises HTTP 403 immediately if role is absent — regardless of token validity.
    Inject with: claims: Annotated[dict, Depends(require_operator)]
    """
    if "operator" not in claims.get(ROLES_CLAIM, []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator role required for this resource.",
        )
    return claims
