"""Gemini API client using the google-genai SDK."""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator

from google import genai
from google.genai import types
from google.oauth2.credentials import Credentials

from ..config import config
from .exceptions import GeminiAPIError, GeminiParseError, GeminiTimeoutError
from .response import GeminiResponse, GeminiStats

logger = logging.getLogger(__name__)


@dataclass
class GeminiRequest:
    """Request configuration for Gemini API.

    Attributes:
        prompt: The query/prompt to send to Gemini
        model: Model to use (default from config)
        system_instruction: Optional system prompt
        temperature: Controls randomness (0.0-1.0)
        max_output_tokens: Maximum tokens to generate
        timeout: Request timeout in seconds
        stream: Enable streaming for long operations
    """

    prompt: str
    model: str | None = None
    system_instruction: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    timeout: int | None = None
    stream: bool = False
    tools: list[Any] | None = None
    safety_settings: Any | None = None


@dataclass
class StreamEvent:
    """Event from streaming response."""

    type: str  # init, message, tool_use, tool_result, result, error
    data: dict = field(default_factory=dict)
    timestamp: str = ""


class GeminiClient:
    """Client for Google's Gemini API using the genai SDK."""

    def __init__(self) -> None:
        """Initialize the Gemini client.

        Prioritizes GOOGLE_API_KEY environment variable.
        Falls back to Gemini CLI OAuth credentials if available.
        Attempts to auto-discover GCP project for Vertex AI if using OAuth.
        """
        self.default_model = config.default_model
        self.fast_model = config.fast_model

        api_key = os.getenv("GOOGLE_API_KEY")
        credentials = None
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")

        if not api_key:
            credentials = self._load_cli_credentials()
            if credentials:
                logger.info("Loaded Gemini CLI OAuth credentials")

                # Auto-discover project if not set and opt-in enabled
                if not project_id and config.auto_discover_project:
                    project_id = self._fetch_project_id(credentials)
                elif not project_id:
                    logger.debug(
                        "GCP project auto-discovery disabled. "
                        "Set GEMINI_MCP_AUTO_DISCOVER_PROJECT=true to enable."
                    )

                if project_id:
                    logger.info(f"Using Vertex AI with project: {project_id}")
                else:
                    logger.warning(
                        "Could not determine Project ID. OAuth may fail if Vertex AI is required."
                    )
            else:
                logger.warning("No authentication found. Set GOOGLE_API_KEY or run 'gemini login'")

        # Initialize client
        try:
            if api_key:
                self.client = genai.Client(api_key=api_key)
                logger.info("Authenticated using API key (Developer API)")
            elif credentials and project_id:
                # OAuth credentials typically require Vertex AI mode in google-genai v1.x
                self.client = genai.Client(
                    credentials=credentials,
                    vertexai=True,
                    project=project_id,
                    location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
                )
                logger.info("Authenticated using OAuth credentials (Vertex AI)")
            elif credentials:
                # Fallback: Try generic init, though this likely fails for Developer API
                self.client = genai.Client(credentials=credentials)
                logger.info("Authenticated using OAuth credentials (Generic)")
            else:
                # Try without credentials (ADC or unauth)
                self.client = genai.Client()
                logger.info("Initialized client with Application Default Credentials")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini Client: {e}")
            # We don't raise here to allow the server to start, but requests will fail
            self.client = None

    def _fetch_project_id(self, creds: Credentials) -> str | None:
        """Fetch the first available project ID using credentials."""
        import requests
        from google.auth.transport.requests import Request

        try:
            if not creds.valid:
                logger.info("Refreshing OAuth credentials...")
                creds.refresh(Request())

            url = "https://cloudresourcemanager.googleapis.com/v1/projects"
            headers = {"Authorization": f"Bearer {creds.token}"}

            # Use a short timeout to not block startup
            resp = requests.get(url, headers=headers, timeout=3.0)
            if resp.status_code == 200:
                projects = resp.json().get("projects", [])
                if projects:
                    return projects[0]["projectId"]
            else:
                logger.warning(f"Failed to list projects: {resp.status_code}")

        except Exception as e:
            logger.warning(f"Project auto-discovery failed: {e}")

        return None

    def _load_cli_credentials(self) -> Credentials | None:
        """Load OAuth credentials from Gemini CLI storage."""
        try:
            creds_path = Path.home() / ".gemini" / "oauth_creds.json"
            if not creds_path.exists():
                return None

            with open(creds_path) as f:
                data = json.load(f)

            return Credentials(
                token=data.get("access_token"),
                refresh_token=data.get("refresh_token"),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=None,
                client_secret=None,
                scopes=data.get("scope", "").split(),
            )
        except Exception as e:
            logger.warning(f"Failed to load Gemini CLI credentials: {e}")
            return None

    async def generate(self, request: GeminiRequest) -> GeminiResponse:
        """Generate content using Gemini API.

        Args:
            request: Request configuration

        Returns:
            GeminiResponse with generated content

        Raises:
            GeminiAPIError: If API call fails
            GeminiParseError: If response parsing fails
        """
        model = request.model or self.default_model
        start_time = time.time()

        try:
            # Configure generation
            gen_config = types.GenerateContentConfig(
                temperature=request.temperature,
                max_output_tokens=request.max_output_tokens,
                system_instruction=request.system_instruction,
                tools=request.tools,
                safety_settings=request.safety_settings,
            )

            # Execute request
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=request.prompt,
                config=gen_config,
            )

            elapsed = time.time() - start_time
            return self._parse_response(response, elapsed, model)

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            if "401" in str(e) or "Unauthenticated" in str(e):
                logger.error("Authentication failed. Run 'gemini login' or set GOOGLE_API_KEY")
            raise GeminiAPIError(f"API request failed: {e}") from e

    async def stream(self, request: GeminiRequest) -> AsyncIterator[StreamEvent]:
        """Stream content generation.

        Args:
            request: Request configuration

        Yields:
            StreamEvent objects with incremental content

        Raises:
            GeminiAPIError: If API call fails
        """
        model = request.model or self.default_model
        start_time = time.time()

        try:
            gen_config = types.GenerateContentConfig(
                temperature=request.temperature,
                max_output_tokens=request.max_output_tokens,
                system_instruction=request.system_instruction,
                tools=request.tools,
                safety_settings=request.safety_settings,
            )

            # Yield init event
            yield StreamEvent(
                type="init",
                data={"model": model},
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )

            # Stream response
            accumulated_text = []
            async for chunk in await self.client.aio.models.generate_content_stream(
                model=model,
                contents=request.prompt,
                config=gen_config,
            ):
                if hasattr(chunk, "text") and chunk.text:
                    accumulated_text.append(chunk.text)
                    yield StreamEvent(
                        type="message",
                        data={"role": "assistant", "content": chunk.text},
                        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    )

            # Yield final result
            elapsed = time.time() - start_time
            yield StreamEvent(
                type="result",
                data={
                    "response": "".join(accumulated_text),
                    "elapsed_seconds": elapsed,
                },
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield StreamEvent(
                type="error",
                data={"error": str(e)},
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            raise GeminiAPIError(f"Streaming failed: {e}") from e

    def _parse_response(self, response: Any, elapsed: float, model: str) -> GeminiResponse:
        """Parse API response into GeminiResponse."""
        try:
            text = response.text if hasattr(response, "text") else ""

            # Extract usage metadata
            usage = getattr(response, "usage_metadata", None)
            stats = GeminiStats(
                prompt_tokens=getattr(usage, "prompt_token_count", 0) if usage else 0,
                response_tokens=(getattr(usage, "candidates_token_count", 0) if usage else 0),
                total_tokens=getattr(usage, "total_token_count", 0) if usage else 0,
                duration_ms=int(elapsed * 1000),
            )

            return GeminiResponse(
                text=text,
                stats=stats,
                elapsed_seconds=elapsed,
                model=model,
            )

        except Exception as e:
            raise GeminiParseError(f"Failed to parse response: {e}") from e

    def get_available_models(self) -> list[str]:
        """Get list of available models."""
        return [
            self.default_model,
            self.fast_model,
            "gemini-3-pro-preview",
            "gemini-3-flash-preview",
        ]


# Global client instance
_client: GeminiClient | None = None


def get_client() -> GeminiClient:
    """Get or create the global Gemini client."""
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client
