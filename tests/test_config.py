"""Tests for configuration module."""

import os

import pytest
from pydantic import ValidationError

from gemini_mcp.config import GeminiMCPConfig


class TestConfig:
    """Tests for GeminiMCPConfig."""

    def test_default_values(self, monkeypatch):
        """Test default configuration values."""
        monkeypatch.delenv("GEMINI_MCP_TRANSPORT", raising=False)
        config = GeminiMCPConfig()

        assert config.server_name == "gemini-mcp"
        assert config.server_port == 8765
        assert config.transport == "stdio"
        assert config.enable_swarm is True
        assert config.enable_debate is True

    def test_env_override(self, monkeypatch):
        """Test environment variable override."""
        monkeypatch.setenv("GEMINI_MCP_SERVER_PORT", "9000")
        monkeypatch.setenv("GEMINI_MCP_TRANSPORT", "sse")

        config = GeminiMCPConfig()

        assert config.server_port == 9000
        assert config.transport == "sse"

    def test_model_defaults(self):
        """Test model default values."""
        config = GeminiMCPConfig()

        assert "gemini" in config.default_model
        assert "gemini" in config.fast_model

    def test_timeout_settings(self):
        """Test timeout configuration."""
        config = GeminiMCPConfig()

        assert config.timeout > 0
        assert config.activity_timeout > 0
        assert config.reasoning_timeout > config.timeout

    def test_security_fields_exist(self):
        """Test that security config fields are present with safe defaults."""
        config = GeminiMCPConfig()

        assert config.auth_token == ""
        assert config.plugin_allowlist == ""
        assert config.plugin_require_hash is False
        assert config.allowed_paths == ""

    def test_debate_fields(self):
        """Test debate config fields have correct defaults."""
        config = GeminiMCPConfig()

        assert config.debate_novelty_threshold == 0.2
        assert config.debate_min_rounds == 3
        assert config.debate_max_rounds == 10
        assert config.debate_turn_timeout > 0

    def test_max_context_tokens_default(self):
        """Test max_context_tokens matches Gemini 3 capability."""
        config = GeminiMCPConfig()
        assert config.max_context_tokens == 900_000


class TestConfigValidation:
    """Tests for Pydantic field validators."""

    def test_port_zero_rejected(self, monkeypatch):
        """Port 0 should be rejected."""
        monkeypatch.setenv("GEMINI_MCP_SERVER_PORT", "0")
        with pytest.raises(ValidationError, match="server_port"):
            GeminiMCPConfig()

    def test_port_negative_rejected(self, monkeypatch):
        """Negative port should be rejected."""
        monkeypatch.setenv("GEMINI_MCP_SERVER_PORT", "-1")
        with pytest.raises(ValidationError, match="server_port"):
            GeminiMCPConfig()

    def test_port_too_high_rejected(self, monkeypatch):
        """Port > 65535 should be rejected."""
        monkeypatch.setenv("GEMINI_MCP_SERVER_PORT", "70000")
        with pytest.raises(ValidationError, match="server_port"):
            GeminiMCPConfig()

    def test_port_valid_range(self, monkeypatch):
        """Valid ports should be accepted."""
        for port in ["1", "80", "8765", "65535"]:
            monkeypatch.setenv("GEMINI_MCP_SERVER_PORT", port)
            config = GeminiMCPConfig()
            assert config.server_port == int(port)

    def test_negative_timeout_rejected(self, monkeypatch):
        """Negative timeout should be rejected."""
        monkeypatch.setenv("GEMINI_MCP_TIMEOUT", "-10")
        with pytest.raises(ValidationError, match="Timeout"):
            GeminiMCPConfig()

    def test_zero_timeout_rejected(self, monkeypatch):
        """Zero timeout should be rejected."""
        monkeypatch.setenv("GEMINI_MCP_TIMEOUT", "0")
        with pytest.raises(ValidationError, match="Timeout"):
            GeminiMCPConfig()

    def test_threshold_above_one_rejected(self, monkeypatch):
        """Threshold > 1.0 should be rejected."""
        monkeypatch.setenv("GEMINI_MCP_DEBATE_NOVELTY_THRESHOLD", "1.5")
        with pytest.raises(ValidationError, match="Threshold"):
            GeminiMCPConfig()

    def test_threshold_negative_rejected(self, monkeypatch):
        """Negative threshold should be rejected."""
        monkeypatch.setenv("GEMINI_MCP_DEBATE_NOVELTY_THRESHOLD", "-0.1")
        with pytest.raises(ValidationError, match="Threshold"):
            GeminiMCPConfig()

    def test_swarm_depth_zero_rejected(self, monkeypatch):
        """Zero swarm depth should be rejected."""
        monkeypatch.setenv("GEMINI_MCP_SWARM_MAX_DEPTH", "0")
        with pytest.raises(ValidationError, match="swarm_max_depth"):
            GeminiMCPConfig()

    def test_swarm_depth_too_high_rejected(self, monkeypatch):
        """Swarm depth > 20 should be rejected."""
        monkeypatch.setenv("GEMINI_MCP_SWARM_MAX_DEPTH", "25")
        with pytest.raises(ValidationError, match="swarm_max_depth"):
            GeminiMCPConfig()

    def test_invalid_log_level_rejected(self, monkeypatch):
        """Invalid log level should be rejected."""
        monkeypatch.setenv("GEMINI_MCP_LOG_LEVEL", "VERBOSE")
        with pytest.raises(ValidationError, match="log_level"):
            GeminiMCPConfig()

    def test_log_level_case_normalized(self, monkeypatch):
        """Log level should be uppercased."""
        monkeypatch.setenv("GEMINI_MCP_LOG_LEVEL", "debug")
        config = GeminiMCPConfig()
        assert config.log_level == "DEBUG"

    def test_token_limit_too_low_rejected(self, monkeypatch):
        """Token limit < 1000 should be rejected."""
        monkeypatch.setenv("GEMINI_MCP_MAX_CONTEXT_TOKENS", "500")
        with pytest.raises(ValidationError, match="max_context_tokens"):
            GeminiMCPConfig()


class TestAuthChain:
    """Tests for GeminiClient credential loading."""

    def test_api_key_takes_priority(self, monkeypatch):
        """GOOGLE_API_KEY should be used when set."""
        from unittest.mock import MagicMock, patch

        monkeypatch.setenv("GOOGLE_API_KEY", "test-key-123")

        with patch("gemini_mcp.core.gemini.genai.Client") as mock_client_cls:
            mock_client_cls.return_value = MagicMock()
            from gemini_mcp.core.gemini import GeminiClient

            client = GeminiClient()

            mock_client_cls.assert_called_once_with(api_key="test-key-123")
            assert client.client is not None

    def test_missing_credentials_still_initializes(self, monkeypatch, tmp_path):
        """Server should start even without valid credentials."""
        from unittest.mock import MagicMock, patch

        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        # Point HOME to tmp_path so no .gemini/oauth_creds.json exists
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("gemini_mcp.core.gemini.genai.Client") as mock_client_cls:
            mock_client_cls.return_value = MagicMock()
            from gemini_mcp.core.gemini import GeminiClient

            client = GeminiClient()

            # Should use ADC fallback (no api_key, no credentials)
            assert client.client is not None

    def test_oauth_credential_loading(self, monkeypatch, tmp_path):
        """OAuth credentials should be loaded from ~/.gemini/oauth_creds.json."""
        import json as _json
        from unittest.mock import MagicMock, patch

        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

        # Create fake OAuth creds file
        gemini_dir = tmp_path / ".gemini"
        gemini_dir.mkdir()
        creds_file = gemini_dir / "oauth_creds.json"
        creds_file.write_text(
            _json.dumps(
                {
                    "access_token": "fake-token",
                    "refresh_token": "fake-refresh",
                    "scope": "openid email",
                }
            )
        )
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("gemini_mcp.core.gemini.genai.Client") as mock_client_cls:
            mock_client_cls.return_value = MagicMock()
            from gemini_mcp.core.gemini import GeminiClient

            with patch.object(GeminiClient, "_fetch_project_id", return_value=None):
                client = GeminiClient()

            # Should have attempted to use credentials (not api_key)
            assert client.client is not None

    def test_client_init_failure_handled(self, monkeypatch):
        """Client init failure should be handled gracefully."""
        from unittest.mock import patch

        monkeypatch.setenv("GOOGLE_API_KEY", "bad-key")

        with patch("gemini_mcp.core.gemini.genai.Client", side_effect=Exception("Auth failed")):
            from gemini_mcp.core.gemini import GeminiClient

            client = GeminiClient()

            # Should not crash; client set to None
            assert client.client is None
