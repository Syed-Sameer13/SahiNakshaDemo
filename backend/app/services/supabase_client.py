import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")
load_dotenv()


def get_supabase_url() -> str:
    return os.getenv("SUPABASE_URL", "").rstrip("/")


def get_supabase_publishable_key() -> str:
    return os.getenv("SUPABASE_PUBLISHABLE_KEY", "")


# For backwards compatibility with module-level references
SUPABASE_URL = get_supabase_url()
SUPABASE_PUBLISHABLE_KEY = get_supabase_publishable_key()


def _headers(access_token: str) -> dict[str, str]:
    url = get_supabase_url()
    key = get_supabase_publishable_key()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY must be configured on the FastAPI server.")
    return {
        "apikey": key,
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
    url = get_supabase_url()
    headers = _headers(access_token)
    if prefer:
        headers["Prefer"] = prefer
    with httpx.Client(timeout=30.0) as client:
        response = client.request(
            method,
            f"{url}/rest/v1/{resource.lstrip('/')}",
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
    url = get_supabase_url()
    key = get_supabase_publishable_key()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY must be configured on the FastAPI server.")
    with httpx.Client(timeout=15.0) as client:
        response = client.get(
            f"{url}/auth/v1/user",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {access_token}",
            },
        )
    if response.status_code != 200:
        raise RuntimeError("Supabase access token is invalid or expired.")
    return response.json()
