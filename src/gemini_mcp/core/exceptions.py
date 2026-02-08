"""Custom exceptions for Gemini MCP Server."""


class GeminiMCPError(Exception):
    """Base exception for Gemini MCP errors."""

    pass


class GeminiAPIError(GeminiMCPError):
    """Error communicating with Gemini API."""

    pass


class GeminiParseError(GeminiMCPError):
    """Error parsing Gemini response."""

    pass


class GeminiTimeoutError(GeminiMCPError):
    """Timeout waiting for Gemini response."""

    pass


class SwarmError(GeminiMCPError):
    """Error in swarm execution."""

    pass


class DebateError(GeminiMCPError):
    """Error in debate execution."""

    pass
