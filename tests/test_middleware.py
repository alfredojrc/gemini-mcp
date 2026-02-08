"""Tests for middleware: rate limiting, request size limits, audit logging."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gemini_mcp.middleware import (
    RateLimitMiddleware,
    RequestSizeLimitMiddleware,
    _TokenBucket,
    audit_event,
)


class TestTokenBucket:
    """Tests for token bucket internals."""

    def test_initial_capacity(self):
        """Bucket starts with full capacity."""
        bucket = _TokenBucket(10.0)
        assert bucket.tokens == 10.0

    def test_last_refill_set(self):
        """Bucket records creation time."""
        before = time.monotonic()
        bucket = _TokenBucket(5.0)
        after = time.monotonic()
        assert before <= bucket.last_refill <= after


class TestRateLimitMiddleware:
    """Tests for rate limiting middleware."""

    def test_disabled_when_rate_zero(self):
        """Rate limit of 0 means disabled."""
        limiter = RateLimitMiddleware(app=MagicMock(), rate=0, burst=20)
        assert limiter.rate == 0

    def test_tokens_per_second_calculation(self):
        """60 requests/min = 1 request/sec."""
        limiter = RateLimitMiddleware(app=MagicMock(), rate=60, burst=10)
        assert limiter.tokens_per_second == pytest.approx(1.0)

    def test_get_client_ip_direct(self):
        """Extract IP from direct connection."""
        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "192.168.1.1"

        ip = RateLimitMiddleware._get_client_ip(request)
        assert ip == "192.168.1.1"

    def test_get_client_ip_forwarded(self):
        """Extract IP from X-Forwarded-For header."""
        request = MagicMock()
        request.headers = {"x-forwarded-for": "10.0.0.1, 10.0.0.2"}

        ip = RateLimitMiddleware._get_client_ip(request)
        assert ip == "10.0.0.1"

    def test_get_client_ip_no_client(self):
        """Handle missing client info."""
        request = MagicMock()
        request.headers = {}
        request.client = None

        ip = RateLimitMiddleware._get_client_ip(request)
        assert ip == "unknown"


class TestRequestSizeLimitMiddleware:
    """Tests for request size limit middleware."""

    def test_disabled_when_zero(self):
        """Size limit of 0 means unlimited."""
        limiter = RequestSizeLimitMiddleware(app=MagicMock(), max_size=0)
        assert limiter.max_size == 0

    def test_max_size_stored(self):
        """Max size is configurable."""
        limiter = RequestSizeLimitMiddleware(app=MagicMock(), max_size=1024)
        assert limiter.max_size == 1024


class TestAuditEvent:
    """Tests for audit logging."""

    def test_noop_when_disabled(self, monkeypatch):
        """audit_event should be a no-op when audit_log is False."""
        monkeypatch.setattr("gemini_mcp.middleware.config.audit_log", False)
        # Should not raise
        audit_event("test_event", tool="test", result="ok")

    def test_logs_when_enabled(self, monkeypatch):
        """audit_event should log when audit_log is True."""
        monkeypatch.setattr("gemini_mcp.middleware.config.audit_log", True)

        from gemini_mcp.middleware import _setup_audit_logger, _audit_logger

        _setup_audit_logger()

        with patch.object(_audit_logger, "handle") as mock_handle:
            audit_event("tool_call", tool="gemini", mode="fast")
            mock_handle.assert_called_once()

            record = mock_handle.call_args[0][0]
            assert hasattr(record, "audit_data")
            assert record.audit_data["tool"] == "gemini"
            assert record.audit_data["mode"] == "fast"
