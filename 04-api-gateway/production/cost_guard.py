"""
Cost Guard — Bảo Vệ Budget LLM (Redis Version)

Mục tiêu: Tránh bill bất ngờ từ LLM API.
- Đếm tokens đã dùng mỗi tháng (lưu trong Redis)
- Cảnh báo khi gần hết budget
- Block khi vượt budget ($10/tháng per user)

Flow:
1. Trước khi gọi LLM: check_budget() -> Raise 402 nếu hết tiền
2. Sau khi gọi LLM: record_usage() -> Update Redis
"""
import os
import time
import logging
import redis
from datetime import datetime
from dataclasses import dataclass
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Giá token (tham khảo)
PRICE_PER_1K_INPUT_TOKENS = 0.00015
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006

@dataclass
class UsageRecord:
    user_id: str
    total_cost_usd: float
    budget_usd: float

class CostGuard:
    def __init__(
        self,
        monthly_budget_usd: float = 10.0,
        warn_at_pct: float = 0.8,
    ):
        self.monthly_budget_usd = monthly_budget_usd
        self.warn_at_pct = warn_at_pct
        
        # Kết nối Redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            self.r = redis.from_url(redis_url, decode_responses=True)
            self.r.ping()
            logger.info(f"CostGuard connected to Redis at {redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}. CostGuard will be disabled or fail.")
            self.r = None

    def _get_keys(self, user_id: str):
        month_key = datetime.now().strftime("%Y-%m")
        return f"cost:{user_id}:{month_key}"

    def check_budget(self, user_id: str) -> None:
        """Kiểm tra budget trong Redis trước khi gọi LLM."""
        if not self.r:
            return # Skip nếu không có Redis (hoặc raise error tùy policy)

        key = self._get_keys(user_id)
        current_cost = float(self.r.get(key) or 0)

        if current_cost >= self.monthly_budget_usd:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "Monthly budget exceeded",
                    "used_usd": round(current_cost, 4),
                    "budget_usd": self.monthly_budget_usd,
                    "resets_at": "Next month",
                },
            )

        if current_cost >= self.monthly_budget_usd * self.warn_at_pct:
            logger.warning(f"User {user_id} has used {current_cost/self.monthly_budget_usd*100:.1f}% of monthly budget")

    def record_usage(self, user_id: str, input_tokens: int, output_tokens: int) -> UsageRecord:
        """Cập nhật chi phí vào Redis sau khi gọi LLM."""
        cost = (input_tokens / 1000 * PRICE_PER_1K_INPUT_TOKENS) + \
               (output_tokens / 1000 * PRICE_PER_1K_OUTPUT_TOKENS)
        
        if not self.r:
            return UsageRecord(user_id, cost, self.monthly_budget_usd)

        key = self._get_keys(user_id)
        # Tăng giá trị trong Redis
        new_total = self.r.incrbyfloat(key, cost)
        
        # Set expiry cho key (32 ngày để chắc chắn qua tháng sau)
        self.r.expire(key, 32 * 24 * 3600)

        logger.info(f"Usage recorded for {user_id}: +${cost:.6f}. Total: ${new_total:.4f}")
        return UsageRecord(user_id, new_total, self.monthly_budget_usd)

    def get_usage(self, user_id: str) -> dict:
        """Lấy thông tin usage hiện tại."""
        if not self.r:
            return {"error": "Redis not connected"}
            
        key = self._get_keys(user_id)
        current_cost = float(self.r.get(key) or 0)
        
        return {
            "user_id": user_id,
            "monthly_cost_usd": round(current_cost, 4),
            "monthly_budget_usd": self.monthly_budget_usd,
            "remaining_usd": round(max(0, self.monthly_budget_usd - current_cost), 4),
            "used_pct": round(current_cost / self.monthly_budget_usd * 100, 1)
        }

# Singleton
cost_guard = CostGuard(monthly_budget_usd=10.0)
