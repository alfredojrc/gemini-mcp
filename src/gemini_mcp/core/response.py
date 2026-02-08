"""Response types for Gemini MCP Server."""

from dataclasses import dataclass, field


@dataclass
class GeminiStats:
    """Statistics from a Gemini API call."""

    prompt_tokens: int = 0
    response_tokens: int = 0
    total_tokens: int = 0
    duration_ms: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "GeminiStats":
        """Create from dictionary."""
        return cls(
            prompt_tokens=data.get("prompt_tokens", data.get("promptTokenCount", 0)),
            response_tokens=data.get("response_tokens", data.get("candidatesTokenCount", 0)),
            total_tokens=data.get("total_tokens", data.get("totalTokenCount", 0)),
            duration_ms=data.get("duration_ms", 0),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "response_tokens": self.response_tokens,
            "total_tokens": self.total_tokens,
            "duration_ms": self.duration_ms,
        }


@dataclass
class GeminiResponse:
    """Response from a Gemini API call."""

    text: str = ""
    stats: GeminiStats | None = None
    error: str | None = None
    raw: dict = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    model: str = ""
    tool_use: dict | None = None

    # Alias for compatibility
    @property
    def content(self) -> str:
        """Alias for text."""
        return self.text

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result = {
            "text": self.text,
            "elapsed_seconds": self.elapsed_seconds,
        }
        if self.stats:
            result["stats"] = self.stats.to_dict()
        if self.error:
            result["error"] = self.error
        if self.model:
            result["model"] = self.model
        if self.tool_use:
            result["tool_use"] = self.tool_use
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "GeminiResponse":
        """Create from dictionary."""
        stats = None
        if "stats" in data:
            stats = GeminiStats.from_dict(data["stats"])
        return cls(
            text=data.get("text", data.get("content", "")),
            stats=stats,
            error=data.get("error"),
            raw=data.get("raw", {}),
            elapsed_seconds=data.get("elapsed_seconds", 0.0),
            model=data.get("model", ""),
            tool_use=data.get("tool_use"),
        )
