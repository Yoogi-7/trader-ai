# apps/api/security.py
from __future__ import annotations
import os
import json
import time
import logging
from typing import Callable, Optional

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
import redis

log = logging.getLogger("security")

# === API Keys / Roles ===
API_KEY_USER = os.getenv("API_KEY_USER", "").strip()
API_KEY_ADMIN = os.getenv("API_KEY_ADMIN", "").strip()

def resolve_role_from_key(key: str | None) -> Optional[str]:
    if not key:
        return None
    if API_KEY_ADMIN and key == API_KEY_ADMIN:
        return "admin"
    if API_KEY_USER and key == API_KEY_USER:
        return "user"
    return None

def require_role(role: str) -> Callable:
    """
    Dependency-style checker usable on routes (FastAPI Depends).
    Example: @router.post("/admin/kill_switch", dependencies=[Depends(require_role("admin"))])
    """
    from fastapi import Depends

    async def _check(request: Request):
        current = getattr(request.state, "role", None)
        if current is None:
            # fallback if middleware not installed
            current = resolve_role_from_key(request.headers.get("X-API-Key"))
        allowed = (current == role) or (role == "user" and current in ("user", "admin"))
        if not allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        return True

    return Depends(_check)

# === Rate Limiter (Redis fixed window) ===
class RateLimiter(BaseHTTPMiddleware):
    """
    Prosty limiter: N żądań na okno (sekundy) per klucz (API key) lub IP.
    Używa Redis (jeśli brak – miękko przepuszcza).
    Dodaje nagłówki X-RateLimit-*.
    """

    def __init__(self, app, capacity: int = 120, window_sec: int = 60, redis_url: str = "redis://redis:6379/0",
                 allowlist_prefixes: tuple[str, ...] = ("/health", "/ws", "/docs", "/openapi.json")):
        super().__init__(app)
        self.capacity = capacity
        self.window = window_sec
        self.redis_url = redis_url
        self.allowlist = allowlist_prefixes
        try:
            self.r = redis.from_url(redis_url, decode_responses=True, socket_timeout=0.5)
            self.r.ping()
        except Exception:
            self.r = None
            log.warning("RateLimiter: Redis not available, limiter is SOFT (no limits).")

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Allowlist (bez limitu i bez auth)
        if any(path.startswith(p) for p in self.allowlist):
            return await self._call_and_audit(request, call_next, allowed=True, limit_headers=None)

        # Ustal klucz tożsamości + ranga
        api_key = request.headers.get("X-API-Key")
        role = resolve_role_from_key(api_key)
        request.state.role = role

        # Brak klucza = brak dostępu
        if role is None:
            return self._deny(status.HTTP_401_UNAUTHORIZED, "missing or invalid API key")

        # Rate limiting
        limit_headers = None
        allowed = True
        if self.r:
            ident = api_key or request.client.host
            now = int(time.time())
            window_start = now - (now % self.window)
            key = f"rl:{ident}:{window_start}"
            try:
                count = self.r.incr(key)
                if count == 1:
                    self.r.expire(key, self.window + 1)
                remaining = max(0, self.capacity - count)
                reset = window_start + self.window - now
                limit_headers = {
                    "X-RateLimit-Limit": str(self.capacity),
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Reset": str(reset),
                }
                if count > self.capacity:
                    allowed = False
            except Exception as e:
                log.warning("RateLimiter Redis error: %s", e)

        if not allowed:
            return self._deny(status.HTTP_429_TOO_MANY_REQUESTS, "rate limit exceeded", limit_headers)

        return await self._call_and_audit(request, call_next, allowed=True, limit_headers=limit_headers)

    async def _call_and_audit(self, request: Request, call_next, allowed: bool, limit_headers: dict | None):
        # Audit log (JSON do stdout)
        try:
            log.info(json.dumps({
                "ts": int(time.time()),
                "path": request.url.path,
                "method": request.method,
                "role": getattr(request.state, "role", None),
                "client": request.client.host if request.client else None,
                "allowed": allowed,
            }))
        except Exception:
            pass

        response = await call_next(request)
        if limit_headers:
            for k, v in limit_headers.items():
                response.headers[k] = v
        return response

    def _deny(self, code: int, msg: str, extra_headers: dict | None = None):
        from starlette.responses import JSONResponse
        payload = {"detail": msg}
        resp = JSONResponse(status_code=code, content=payload)
        if extra_headers:
            for k, v in extra_headers.items():
                resp.headers[k] = v
        return resp
