"""ASGI middleware for rate limiting, request size limits, and audit logging."""

import json
import logging
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .config import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Audit Logger — structured JSON logging for tool invocations
# ---------------------------------------------------------------------------
_audit_logger = logging.getLogger("gemini_mcp.audit")


def _setup_audit_logger() -> None:
    """Configure the audit logger with JSON formatting to stdout."""
    if _audit_logger.handlers:
        return  # Already configured

    import sys

    class _JSONFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            from datetime import datetime

            entry: dict = {
                "timestamp": datetime.now(UTC).isoformat(),
                "level": record.levelname,
                "event": record.getMessage(),
            }
            if hasattr(record, "audit_data"):
                entry.update(record.audit_data)
            return json.dumps(entry)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JSONFormatter())
    _audit_logger.addHandler(handler)
    _audit_logger.setLevel(logging.INFO)
    _audit_logger.propagate = False


def audit_event(event: str, **fields: str) -> None:
    """Log a structured audit event (no-op if audit_log is disabled)."""
    if not config.audit_log:
        return
    record = _audit_logger.makeRecord(_audit_logger.name, logging.INFO, "", 0, event, (), None)
    record.audit_data = fields  # type: ignore[attr-defined]
    _audit_logger.handle(record)


# Initialize audit logger if enabled
if config.audit_log:
    _setup_audit_logger()


# ---------------------------------------------------------------------------
# Token Bucket Rate Limiter — in-memory, zero external dependencies
# ---------------------------------------------------------------------------
class _TokenBucket:
    """Per-client token bucket for rate limiting."""

    __slots__ = ("tokens", "last_refill")

    def __init__(self, capacity: float) -> None:
        self.tokens = capacity
        self.last_refill = time.monotonic()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory token bucket rate limiter.

    Configured via:
      GEMINI_MCP_RATE_LIMIT — requests per minute (0 = disabled)
      GEMINI_MCP_RATE_LIMIT_BURST — max burst capacity
    """

    def __init__(self, app: Any, rate: int = 0, burst: int = 20) -> None:
        super().__init__(app)
        self.rate = rate  # requests per minute
        self.burst = burst
        self.tokens_per_second = rate / 60.0
        self._buckets: dict[str, _TokenBucket] = defaultdict(lambda: _TokenBucket(float(burst)))

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
        if self.rate <= 0:
            return await call_next(request)

        # Health endpoint is always exempt
        if request.url.path == "/health":
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        bucket = self._buckets[client_ip]

        # Refill tokens
        now = time.monotonic()
        elapsed = now - bucket.last_refill
        bucket.tokens = min(float(self.burst), bucket.tokens + elapsed * self.tokens_per_second)
        bucket.last_refill = now

        if bucket.tokens < 1.0:
            retry_after = int((1.0 - bucket.tokens) / self.tokens_per_second) + 1
            audit_event(
                "rate_limited",
                client_ip=client_ip,
                path=request.url.path,
            )
            return JSONResponse(
                {"error": "Rate limit exceeded"},
                status_code=429,
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.rate),
                    "X-RateLimit-Remaining": "0",
                },
            )

        bucket.tokens -= 1.0

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.rate)
        response.headers["X-RateLimit-Remaining"] = str(int(bucket.tokens))
        return response

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"


# ---------------------------------------------------------------------------
# Request Size Limit Middleware
# ---------------------------------------------------------------------------
class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests with bodies exceeding the configured size limit.

    Configured via GEMINI_MCP_MAX_REQUEST_SIZE (bytes, 0 = unlimited).
    """

    def __init__(self, app: Any, max_size: int = 0) -> None:
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
        if self.max_size <= 0:
            return await call_next(request)

        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_size:
            return JSONResponse(
                {"error": f"Request body too large. " f"Maximum: {self.max_size:,} bytes"},
                status_code=413,
            )

        return await call_next(request)
