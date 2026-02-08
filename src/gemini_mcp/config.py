"""Configuration management for Gemini MCP Server."""

from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings


class GeminiMCPConfig(BaseSettings):
    """Configuration for Gemini MCP Server.

    All settings can be overridden via environment variables with GEMINI_MCP_ prefix.
    Example: GEMINI_MCP_TRANSPORT=sse
    """

    # =========================================================================
    # Server Settings
    # =========================================================================
    server_name: str = "gemini-mcp"
    server_host: str = "0.0.0.0"
    server_port: int = 8765
    transport: Literal["stdio", "sse", "streamable-http"] = "stdio"

    # =========================================================================
    # Gemini Model Settings
    # =========================================================================
    # Default model for standard queries (latest reasoning model)
    default_model: str = "gemini-3-pro-preview"
    # Fast model for quick responses
    fast_model: str = "gemini-3-flash-preview"

    # Timeout settings (in seconds)
    timeout: int = 300  # 5 minutes default
    activity_timeout: int = 600  # 10 minutes between streaming events
    reasoning_timeout: int = 900  # 15 minutes for deep reasoning

    # Context settings (Gemini has 1M token window)
    max_context_tokens: int = 900_000  # Leave buffer from 1M

    # =========================================================================
    # Feature Toggles
    # =========================================================================
    enable_swarm: bool = True
    enable_debate: bool = True

    # =========================================================================
    # Search Settings
    # =========================================================================
    web_search_grounding: bool = True
    parallel_search_timeout: int = 60

    # =========================================================================
    # Debate Settings
    # =========================================================================
    debate_max_rounds: int = 10
    debate_min_rounds: int = 3
    debate_novelty_threshold: float = 0.2
    debate_repetition_threshold: float = 0.7
    debate_turn_timeout: int = 180

    # =========================================================================
    # Swarm Settings
    # =========================================================================
    swarm_max_depth: int = 3  # Maximum recursion depth
    swarm_max_agents: int = 10  # Maximum concurrent agents

    # =========================================================================
    # Storage Paths
    # =========================================================================
    data_dir: Path = Path.home() / ".gemini-mcp"
    context_cache_dir: Path = Path.home() / ".gemini-mcp" / "context-cache"
    debate_storage_dir: Path = Path.home() / ".gemini-mcp" / "debates"
    log_dir: Path = Path.home() / ".gemini-mcp" / "logs"

    # =========================================================================
    # Security
    # =========================================================================
    # Optional bearer token — when set, all HTTP requests must include
    # "Authorization: Bearer <token>".  When empty (default), no auth
    # is enforced (suitable for local stdio usage).
    auth_token: str = ""

    # Comma-separated allowlist of plugin filenames (empty = allow all)
    plugin_allowlist: str = ""

    # Require SHA-256 sidecar files for plugins (true/false)
    plugin_require_hash: bool = False

    # Colon-separated allowed base directories for file analysis
    # (empty = CWD + /tmp + $HOME)
    allowed_paths: str = ""

    # Auto-discover GCP project on startup (makes external HTTP call)
    auto_discover_project: bool = False

    # =========================================================================
    # Rate Limiting
    # =========================================================================
    # Requests per minute per client IP (0 = disabled)
    rate_limit: int = 0
    # Burst capacity (max concurrent before throttling)
    rate_limit_burst: int = 20
    # Maximum request body size in bytes (0 = unlimited, default 10MB)
    max_request_size: int = 10 * 1024 * 1024

    # =========================================================================
    # Logging
    # =========================================================================
    log_level: str = "INFO"
    log_usage: bool = True
    # Enable structured JSON audit logging for tool invocations
    audit_log: bool = False

    # =========================================================================
    # Validators — bounds checking for numeric / enum fields
    # =========================================================================
    @field_validator("server_port")
    @classmethod
    def _port_range(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError(f"server_port must be 1-65535, got {v}")
        return v

    @field_validator("timeout", "activity_timeout", "reasoning_timeout",
                     "debate_turn_timeout", "parallel_search_timeout")
    @classmethod
    def _positive_timeout(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"Timeout must be >= 1 second, got {v}")
        return v

    @field_validator("max_context_tokens")
    @classmethod
    def _token_limit(cls, v: int) -> int:
        if v < 1000:
            raise ValueError(f"max_context_tokens must be >= 1000, got {v}")
        return v

    @field_validator("debate_novelty_threshold", "debate_repetition_threshold")
    @classmethod
    def _threshold_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"Threshold must be 0.0-1.0, got {v}")
        return v

    @field_validator("swarm_max_depth")
    @classmethod
    def _depth_range(cls, v: int) -> int:
        if not (1 <= v <= 20):
            raise ValueError(f"swarm_max_depth must be 1-20, got {v}")
        return v

    @field_validator("swarm_max_agents")
    @classmethod
    def _agents_range(cls, v: int) -> int:
        if not (1 <= v <= 50):
            raise ValueError(f"swarm_max_agents must be 1-50, got {v}")
        return v

    @field_validator("log_level")
    @classmethod
    def _valid_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid:
            raise ValueError(f"log_level must be one of {valid}, got {v}")
        return v.upper()

    @field_validator("rate_limit", "rate_limit_burst")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError(f"Value must be >= 0, got {v}")
        return v

    @field_validator("max_request_size")
    @classmethod
    def _request_size(cls, v: int) -> int:
        if v < 0:
            raise ValueError(f"max_request_size must be >= 0, got {v}")
        return v

    model_config = {
        "env_prefix": "GEMINI_MCP_",
        "env_file": ".env",
        "extra": "ignore",
    }


# Global configuration instance
config = GeminiMCPConfig()
