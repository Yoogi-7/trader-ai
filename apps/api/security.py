
import time
from fastapi import Request

class RateLimiter:
    def __init__(self, max_per_minute: int = 120):
        self.max_per_minute = max_per_minute

    async def __call__(self, request: Request, call_next):
        # Simple placeholder limiter (can be replaced with redis)
        return await call_next(request)
