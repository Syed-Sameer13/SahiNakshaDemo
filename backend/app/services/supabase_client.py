import os
from typing import Any

import httpx

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")


def _headers(access_token: str) -> dict[str, str]:
    if not SUPABASE_URL or not SUPABASE_PUBLISHABLE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY must be configured on the FastAPI server.")
    return {
        "apikey": SUPABASE_PUBLISHABLE_KEY,
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def supabase_rest(
    method: str,
    resource: str,
    access_token: str,
    *,
    params: dict[str, Any] | None = None,
    json: Any = None,
    prefer: str | None = None,
) -> Any:
    headers = _headers(access_token)
    if prefer:
        headers["Prefer"] = prefer
    with httpx.Client(timeout=30.0) as client:
        response = client.request(
            method,
            f"{SUPABASE_URL}/rest/v1/{resource.lstrip('/')}",
            headers=headers,
            params=params,
            json=json,
        )
    if response.status_code >= 400:
        detail = response.text[:1000]
        raise RuntimeError(f"Supabase {method} {resource} failed ({response.status_code}): {detail}")
    if not response.content:
        return None
    return response.json()


def supabase_auth_user(access_token: str) -> dict[str, Any]:
    if not SUPABASE_URL or not SUPABASE_PUBLISHABLE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY must be configured on the FastAPI server.")
    with httpx.Client(timeout=15.0) as client:
        response = client.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "apikey": SUPABASE_PUBLISHABLE_KEY,
                "Authorization": f"Bearer {access_token}",
            },
        )
    if response.status_code != 200:
        raise RuntimeError("Supabase access token is invalid or expired.")
    return response.json()
