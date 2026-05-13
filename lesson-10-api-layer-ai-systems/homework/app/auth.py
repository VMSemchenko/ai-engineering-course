"""API key authentication and tier resolution."""

from fastapi import Request, HTTPException

from .config import API_KEYS, TIERS


def authenticate(request: Request) -> dict:
    """Validate API key and return tier info.

    Returns dict with keys: api_key, tier_name, token_limit, models
    Raises HTTPException 401 if key is missing or invalid.
    """
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    tier_name = API_KEYS.get(api_key)
    if tier_name is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    tier = TIERS[tier_name]
    return {
        "api_key": api_key,
        "tier_name": tier_name,
        "token_limit": tier["token_limit"],
        "models": tier["models"],
    }
