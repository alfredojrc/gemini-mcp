"""Tests for core tools."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gemini_mcp.tools.core import gemini, analyze, search


class TestGeminiTool:
    """Tests for the gemini tool."""

    @pytest.mark.asyncio
    async def test_models_mode(self):
        """Test models listing mode."""
        result = await gemini(prompt="list models", mode="models")

        assert "models" in result
        assert "default_model" in result
        assert isinstance(result["models"], list)

    @pytest.mark.asyncio
    async def test_fast_mode_prompt(self):
        """Test fast mode creates correct prompt."""
        with patch("gemini_mcp.tools.core.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "Test response"
            mock_response.to_dict.return_value = {"text": "Test response"}
            mock_client.generate = AsyncMock(return_value=mock_response)
            mock_client.fast_model = "gemini-3-flash-preview"
            mock_client.default_model = "gemini-3-pro-preview"
            mock_get_client.return_value = mock_client

            result = await gemini(prompt="Test prompt", mode="fast")

            assert result == "Test response"
            mock_client.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_reasoning_mode_returns_dict(self):
        """Reasoning mode should return a dict with metadata."""
        with patch("gemini_mcp.tools.core.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "Deep analysis"
            mock_response.to_dict.return_value = {
                "text": "Deep analysis",
                "model": "pro",
            }
            mock_client.generate = AsyncMock(return_value=mock_response)
            mock_client.default_model = "gemini-3-pro-preview"
            mock_get_client.return_value = mock_client

            result = await gemini(prompt="Analyze this", mode="reasoning")

            assert isinstance(result, dict)
            assert "text" in result

    @pytest.mark.asyncio
    async def test_token_limit_rejection(self):
        """Huge prompts should be rejected before API call."""
        huge_prompt = "x" * 4_000_000
        result = await gemini(prompt=huge_prompt, mode="fast")
        assert isinstance(result, dict)
        assert "error" in result
        assert "too large" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_context_parameter(self):
        """Context should be included in the prompt."""
        with patch("gemini_mcp.tools.core.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "Response with context"
            mock_client.generate = AsyncMock(return_value=mock_response)
            mock_client.fast_model = "gemini-3-flash-preview"
            mock_get_client.return_value = mock_client

            result = await gemini(prompt="Question", mode="fast", context="Important context")
            assert result == "Response with context"

            # Verify the context was passed in the prompt
            call_args = mock_client.generate.call_args[0][0]
            assert "Important context" in call_args.prompt


class TestAnalyzeTool:
    """Tests for the analyze tool."""

    @pytest.mark.asyncio
    async def test_inline_code_detection(self, sample_code):
        """Test detection of inline code."""
        with patch("gemini_mcp.tools.core.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "Code analysis result"
            mock_client.generate = AsyncMock(return_value=mock_response)
            mock_client.default_model = "gemini-3-pro-preview"
            mock_get_client.return_value = mock_client

            result = await analyze(
                target=sample_code,
                instruction="Review this code",
                focus="general",
            )

            assert "analysis result" in result.lower()

    @pytest.mark.asyncio
    async def test_file_not_found(self):
        """Test handling of non-existent file."""
        result = await analyze(
            target="/nonexistent/file.py",
            instruction="Review",
            focus="general",
        )

        assert isinstance(result, dict)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_sensitive_path_blocked(self):
        """Sensitive paths should be blocked."""
        result = await analyze(
            target="/etc/shadow",
            instruction="Review",
            focus="security",
        )
        assert isinstance(result, dict)
        assert "error" in result
        assert "denied" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_binary_file_rejected(self):
        """Binary files should be rejected."""
        with tempfile.NamedTemporaryFile(suffix=".png", dir="/tmp", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\n")
            f.flush()
            try:
                result = await analyze(
                    target=f.name,
                    instruction="Review",
                    focus="general",
                )
                assert isinstance(result, dict)
                assert "error" in result
                assert "binary" in result["error"].lower()
            finally:
                Path(f.name).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_diff_detection(self):
        """PR diffs should be detected and reviewed."""
        diff = "diff --git a/file.py b/file.py\n+added line"
        with patch("gemini_mcp.tools.core.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "Diff review"
            mock_response.elapsed_seconds = 1.0
            mock_client.generate = AsyncMock(return_value=mock_response)
            mock_client.default_model = "gemini-3-pro-preview"
            mock_get_client.return_value = mock_client

            result = await analyze(target=diff, instruction="Review PR", focus="general")
            assert isinstance(result, dict)
            assert "review" in result


class TestSearchTool:
    """Tests for the search tool."""

    @pytest.mark.asyncio
    async def test_quick_search(self):
        """Test quick search mode."""
        with patch("gemini_mcp.tools.core.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "Search results"
            mock_response.elapsed_seconds = 1.5
            mock_client.generate = AsyncMock(return_value=mock_response)
            mock_client.default_model = "gemini-3-pro-preview"
            mock_get_client.return_value = mock_client

            result = await search(query="Python async", depth="quick")

            assert "query" in result
            assert result["depth"] == "quick"

    @pytest.mark.asyncio
    async def test_deep_search(self):
        """Test deep search mode."""
        with patch("gemini_mcp.tools.core.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "Deep research results"
            mock_response.elapsed_seconds = 5.0
            mock_client.generate = AsyncMock(return_value=mock_response)
            mock_client.default_model = "gemini-3-pro-preview"
            mock_get_client.return_value = mock_client

            result = await search(query="ML trading", depth="deep")

            assert result["depth"] == "deep"
            assert "research" in result

    @pytest.mark.asyncio
    async def test_docs_search(self):
        """Test docs search mode."""
        with patch("gemini_mcp.tools.core.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "Library docs"
            mock_response.elapsed_seconds = 1.0
            mock_client.generate = AsyncMock(return_value=mock_response)
            mock_client.default_model = "gemini-3-pro-preview"
            mock_get_client.return_value = mock_client

            result = await search(query="pandas", depth="docs")

            assert result["depth"] == "docs"
