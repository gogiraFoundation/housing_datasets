from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from housing_api.settings import api_keys, metrics_require_key

_bearer = HTTPBearer(auto_error=False)


def _keys_equal(a: str, b: str) -> bool:
    """Constant-time comparison for API keys; avoids ValueError on length mismatch.

    ``hmac.compare_digest`` raises when lengths differ; treat that as non-match.
    """
    try:
        return hmac.compare_digest(a, b)
    except ValueError:
        return False


def require_api_keys_configured() -> None:
    if not api_keys():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is not configured (set HOUSING_API_KEYS).",
        )


def _extract_key(
    request: Request,
    creds: HTTPAuthorizationCredentials | None,
) -> str | None:
    if creds and creds.scheme.lower() == "bearer" and creds.credentials:
        return creds.credentials
    x_key = request.headers.get("x-api-key")
    if x_key:
        return x_key.strip()
    return None


def verify_api_key(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    require_api_keys_configured()
    key = _extract_key(request, creds)
    if not key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    valid = api_keys()
    if not any(_keys_equal(key, v) for v in valid):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Optional: identify key by index for logs (prefix only, no secret)
    for i, v in enumerate(valid):
        if _keys_equal(key, v):
            request.state.api_key_id = f"key_{i + 1}"
            break
    else:
        request.state.api_key_id = "unknown"
    return key


def enforce_metrics_auth(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> None:
    """When ``HOUSING_API_METRICS_REQUIRE_KEY`` is set, require the same auth as dataset routes."""
    if not metrics_require_key():
        return None
    verify_api_key(request, creds)
    return None
