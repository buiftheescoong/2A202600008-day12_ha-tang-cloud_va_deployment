import redis
from datetime import datetime
from fastapi import HTTPException
from .config import settings

try:
    _redis = redis.from_url(settings.redis_url, decode_responses=True)
    _redis.ping()
    USE_REDIS = True
except Exception:
    USE_REDIS = False
    _memory_budget = {}

def check_budget(user_id: str, estimated_cost: float = 0.002): # Default cost per call
    """
    Check if user has remaining monthly budget.
    """
    month_key = datetime.now().strftime("%Y-%m")
    key = f"budget:{user_id}:{month_key}"
    
    if USE_REDIS:
        current = float(_redis.get(key) or 0)
        if current + estimated_cost > settings.monthly_budget_usd:
            raise HTTPException(
                status_code=402, 
                detail="Monthly budget exceeded. Please contact support."
            )
        
        # Increment and set expiry
        _redis.incrbyfloat(key, estimated_cost)
        _redis.expire(key, 32 * 24 * 3600) # 32 days
    else:
        current = _memory_budget.get(key, 0.0)
        if current + estimated_cost > settings.monthly_budget_usd:
            raise HTTPException(status_code=402, detail="Budget exceeded.")
        _memory_budget[key] = current + estimated_cost
