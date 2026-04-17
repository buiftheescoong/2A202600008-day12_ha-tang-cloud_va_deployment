from fastapi import Header, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from .config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(x_api_key: str = Security(api_key_header)):
    """
    Verify the API Key provided in the X-API-Key header.
    Returns the user_id (for this lab, we treat the key prefix as user_id).
    """
    if not x_api_key or x_api_key != settings.agent_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key."
        )
    # Simple logic: use the first 8 chars of the key as user_id for tracking
    return f"user_{x_api_key[:8]}"
