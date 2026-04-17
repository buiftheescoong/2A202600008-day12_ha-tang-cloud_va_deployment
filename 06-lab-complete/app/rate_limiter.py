import time
import redis
from fastapi import HTTPException
from .config import settings

# Initialize Redis client
try:
    _redis = redis.from_url(settings.redis_url, decode_responses=True)
    _redis.ping()
    USE_REDIS = True
except Exception:
    USE_REDIS = False
    _memory_window = {} # Fallback for local dev without redis

def check_rate_limit(user_id: str):
    """
    Sliding window rate limiter using Redis.
    """
    now = time.time()
    key = f"rate_limit:{user_id}"
    
    if USE_REDIS:
        # Remove old requests outside the 1-minute window
        _redis.zremrangebyscore(key, 0, now - 60)
        
        # Count requests in the current window
        count = _redis.zcard(key)
        
        if count >= settings.rate_limit_per_minute:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded ({settings.rate_limit_per_minute} req/min).",
                headers={"Retry-After": "60"}
            )
        
        # Add the current request
        _redis.zadd(key, {str(now): now})
        _redis.expire(key, 60)
    else:
        # Simple memory fallback logic (non-scalable)
        window = _memory_window.get(user_id, [])
        window = [t for t in window if t > now - 60]
        if len(window) >= settings.rate_limit_per_minute:
            raise HTTPException(status_code=429, detail="Rate limit exceeded.")
        window.append(now)
        _memory_window[user_id] = window
