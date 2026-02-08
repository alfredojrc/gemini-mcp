"""Pure ASGI middleware for authentication, rate limiting, request size limits, and audit logging.

All middleware classes use the raw ASGI ``(scope, receive, send)`` protocol
instead of Starlette's ``BaseHTTPMiddleware``, which is known to:
- Buffer entire streaming responses into memory (breaks SSE)
- Block background tasks until the response stream completes
- Break ``ContextVar`` propagation across middleware boundaries

Ref: https://github.com/encode/starlette/discussions/1729
"""

import hmac
import json
import logging
import time
from typing import Any

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
            from datetime import UTC, datetime

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
# ASGI JSON response helper
# ---------------------------------------------------------------------------
async def _send_json(
    send: Any,
    status_code: int,
    body: dict,
    extra_headers: list[tuple[bytes, bytes]] | None = None,
) -> None:
    """Send a JSON response via raw ASGI protocol."""
    content = json.dumps(body).encode()
    headers: list[tuple[bytes, bytes]] = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(content)).encode()),
    ]
    if extra_headers:
        headers.extend(extra_headers)
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": headers,
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": content,
        }
    )


# ---------------------------------------------------------------------------
# Bearer Token Auth Middleware (pure ASGI)
# ---------------------------------------------------------------------------
class BearerAuthMiddleware:
    """Pure ASGI middleware for Bearer token authentication.

    - Uses ``hmac.compare_digest`` for constant-time token comparison
    - Case-insensitive "Bearer" prefix per RFC 7235
    - ``/health`` endpoint exempt for Docker probes
    """

    def __init__(self, app: Any, token: str = "") -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path == "/health":
            await self.app(scope, receive, send)
            return

        # Extract Authorization header (ASGI headers are bytes)
        auth_header = ""
        for key, value in scope.get("headers", []):
            if key == b"authorization":
                auth_header = value.decode("latin-1")
                break

        # Case-insensitive "Bearer " prefix per RFC 7235
        valid = False
        if len(auth_header) > 7 and auth_header[:7].lower() == "bearer ":
            provided_token = auth_header[7:]
            valid = hmac.compare_digest(provided_token, self.token)

        if not valid:
            await _send_json(
                send,
                401,
                {"error": "unauthorized"},
                [(b"www-authenticate", b"Bearer")],
            )
            return

        await self.app(scope, receive, send)


# ---------------------------------------------------------------------------
# Token Bucket Rate Limiter — in-memory with LRU eviction (pure ASGI)
# ---------------------------------------------------------------------------
class _TokenBucket:
    """Per-client token bucket for rate limiting."""

    __slots__ = ("tokens", "last_refill")

    def __init__(self, capacity: float) -> None:
        self.tokens = capacity
        self.last_refill = time.monotonic()


# Maximum tracked client IPs to prevent memory exhaustion from rotating-IP DDoS.
_MAX_RATE_LIMIT_BUCKETS = 10_000


class RateLimitMiddleware:
    """Pure ASGI token bucket rate limiter with LRU eviction.

    Configured via:
      GEMINI_MCP_RATE_LIMIT — requests per minute (0 = disabled)
      GEMINI_MCP_RATE_LIMIT_BURST — max burst capacity

    Evicts the oldest (least-recently-refilled) bucket when the bucket count
    exceeds ``_MAX_RATE_LIMIT_BUCKETS``, preventing unbounded memory growth
    from rotating-IP attacks.
    """

    def __init__(self, app: Any, rate: int = 0, burst: int = 20) -> None:
        self.app = app
        self.rate = rate
        self.burst = burst
        self.tokens_per_second = rate / 60.0
        self._buckets: dict[str, _TokenBucket] = {}

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or self.rate <= 0:
            await self.app(scope, receive, send)
            return

        # Health endpoint is always exempt
        path = scope.get("path", "")
        if path == "/health":
            await self.app(scope, receive, send)
            return

        client_ip = self._get_client_ip(scope)
        bucket = self._get_or_create_bucket(client_ip)

        # Refill tokens
        now = time.monotonic()
        elapsed = now - bucket.last_refill
        bucket.tokens = min(float(self.burst), bucket.tokens + elapsed * self.tokens_per_second)
        bucket.last_refill = now

        if bucket.tokens < 1.0:
            retry_after = int((1.0 - bucket.tokens) / self.tokens_per_second) + 1
            audit_event("rate_limited", client_ip=client_ip, path=path)
            await _send_json(
                send,
                429,
                {"error": "Rate limit exceeded"},
                [
                    (b"retry-after", str(retry_after).encode()),
                    (b"x-ratelimit-limit", str(self.rate).encode()),
                    (b"x-ratelimit-remaining", b"0"),
                ],
            )
            return

        bucket.tokens -= 1.0
        remaining = str(int(bucket.tokens))

        # Inject rate-limit headers into the response
        async def send_with_headers(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-ratelimit-limit", str(self.rate).encode()))
                headers.append((b"x-ratelimit-remaining", remaining.encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)

    def _get_or_create_bucket(self, client_ip: str) -> _TokenBucket:
        """Get existing bucket or create new one with LRU eviction."""
        if client_ip in self._buckets:
            return self._buckets[client_ip]

        # Evict oldest (least-recently-refilled) entry if at capacity
        if len(self._buckets) >= _MAX_RATE_LIMIT_BUCKETS:
            oldest_key = min(self._buckets, key=lambda k: self._buckets[k].last_refill)
            del self._buckets[oldest_key]

        self._buckets[client_ip] = _TokenBucket(float(self.burst))
        return self._buckets[client_ip]

    @staticmethod
    def _get_client_ip(scope: dict) -> str:
        """Extract client IP from ASGI scope headers."""
        for key, value in scope.get("headers", []):
            if key == b"x-forwarded-for":
                return value.decode("latin-1").split(",")[0].strip()
        client = scope.get("client")
        if client:
            return client[0]
        return "unknown"


# ---------------------------------------------------------------------------
# Request Size Limit Middleware (pure ASGI, handles chunked encoding)
# ---------------------------------------------------------------------------
class _RequestTooLargeError(Exception):
    """Raised internally when request body exceeds size limit."""


class RequestSizeLimitMiddleware:
    """Pure ASGI middleware to reject oversized request bodies.

    Checks both ``Content-Length`` header (fast reject) and actual streamed
    body size (handles chunked transfer encoding).

    Configured via GEMINI_MCP_MAX_REQUEST_SIZE (bytes, 0 = unlimited).
    """

    def __init__(self, app: Any, max_size: int = 0) -> None:
        self.app = app
        self.max_size = max_size

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or self.max_size <= 0:
            await self.app(scope, receive, send)
            return

        # Quick reject via Content-Length header
        for key, value in scope.get("headers", []):
            if key == b"content-length":
                try:
                    if int(value) > self.max_size:
                        await _send_json(
                            send,
                            413,
                            {"error": f"Request body too large. Maximum: {self.max_size:,} bytes"},
                        )
                        return
                except ValueError:
                    pass
                break

        # Wrap receive to enforce limit on streamed/chunked bodies
        body_size = 0
        response_started = False

        async def size_checked_receive() -> dict:
            nonlocal body_size
            message = await receive()
            if message.get("type") == "http.request":
                body_size += len(message.get("body", b""))
                if body_size > self.max_size:
                    raise _RequestTooLargeError()
            return message

        async def tracked_send(message: dict) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, size_checked_receive, tracked_send)
        except _RequestTooLargeError:
            if not response_started:
                await _send_json(
                    send,
                    413,
                    {"error": f"Request body too large. Maximum: {self.max_size:,} bytes"},
                )
