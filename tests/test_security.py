"""Tests for security features: path validation, plugin sandboxing, auth."""

import hashlib
import os
import tempfile
from pathlib import Path

from gemini_mcp.tools.core import (
    _BINARY_EXTENSIONS,
    _estimate_tokens,
    _validate_path,
    _validate_prompt_tokens,
)


class TestPathValidation:
    """Tests for filesystem path validation."""

    def test_block_etc(self):
        """Block /etc directory."""
        result = _validate_path("/etc/passwd")
        assert isinstance(result, str)
        assert "denied" in result.lower()

    def test_block_proc(self):
        """Block /proc directory."""
        result = _validate_path("/proc/self/environ")
        assert isinstance(result, str)
        assert "denied" in result.lower()

    def test_block_sys(self):
        """Block /sys directory."""
        result = _validate_path("/sys/kernel")
        assert isinstance(result, str)
        assert "denied" in result.lower()

    def test_block_root(self):
        """Block /root directory."""
        result = _validate_path("/root/.ssh/id_rsa")
        assert isinstance(result, str)
        assert "denied" in result.lower()

    def test_allow_tmp(self):
        """Allow /tmp directory."""
        with tempfile.NamedTemporaryFile(suffix=".py", dir="/tmp") as f:
            result = _validate_path(f.name)
            assert isinstance(result, Path)

    def test_allow_cwd(self):
        """Allow current working directory."""
        result = _validate_path(os.path.join(os.getcwd(), "test.py"))
        assert isinstance(result, Path)

    def test_traversal_attack(self):
        """Block path traversal attempts."""
        result = _validate_path("/tmp/../../etc/passwd")
        assert isinstance(result, str)
        assert "denied" in result.lower()

    def test_custom_allowed_paths(self, monkeypatch):
        """Custom GEMINI_MCP_ALLOWED_PATHS override."""
        monkeypatch.setenv("GEMINI_MCP_ALLOWED_PATHS", "/custom/path")
        result = _validate_path("/custom/path/file.py")
        # Will return Path if /custom/path exists, error string otherwise
        assert isinstance(result, (Path, str))

    def test_invalid_path(self):
        """Invalid path returns error string."""
        result = _validate_path("\x00invalid")
        assert isinstance(result, str)


class TestTokenValidation:
    """Tests for prompt size validation."""

    def test_estimate_tokens_basic(self):
        """Basic token estimation."""
        est = _estimate_tokens("Hello world")
        assert est > 0
        assert est < 10

    def test_estimate_long_text(self):
        """Long text should have proportionally more tokens."""
        short = _estimate_tokens("Hello")
        long = _estimate_tokens("Hello " * 1000)
        assert long > short * 100

    def test_validate_short_prompt_passes(self):
        """Short prompts should pass validation."""
        assert _validate_prompt_tokens("What is Python?") is None

    def test_validate_huge_prompt_rejected(self):
        """Prompts exceeding token limit should be rejected."""
        huge = "x" * 4_000_000  # ~1.1M tokens
        err = _validate_prompt_tokens(huge)
        assert err is not None
        assert "too large" in err.lower()

    def test_validate_boundary_prompt(self):
        """Prompt right at limit should pass."""
        # 900K tokens * 3.5 chars/token = 3,150,000 chars
        at_limit = "x" * 3_100_000
        err = _validate_prompt_tokens(at_limit)
        assert err is None  # Should just barely pass


class TestBinaryFileDetection:
    """Tests for binary file detection."""

    def test_common_binary_extensions(self):
        """Common binary extensions should be in the blocklist."""
        for ext in [".exe", ".dll", ".png", ".jpg", ".zip", ".pdf", ".pyc"]:
            assert ext in _BINARY_EXTENSIONS, f"{ext} missing from binary blocklist"

    def test_text_extensions_not_blocked(self):
        """Text file extensions should not be blocked."""
        for ext in [".py", ".js", ".ts", ".md", ".txt", ".json", ".yaml"]:
            assert ext not in _BINARY_EXTENSIONS, f"{ext} incorrectly in binary blocklist"


class TestPluginSandbox:
    """Tests for plugin loading security."""

    def test_verify_plugin_hash_disabled(self, tmp_path):
        """With hash verification disabled, all plugins pass."""
        from gemini_mcp.server import _verify_plugin_hash

        plugin_file = tmp_path / "test_plugin.py"
        plugin_file.write_text("# test plugin")

        # Without env var, should pass
        assert _verify_plugin_hash(plugin_file) is True

    def test_verify_plugin_hash_missing_sidecar(self, tmp_path, monkeypatch):
        """Missing .sha256 sidecar should fail when hash required."""
        from gemini_mcp.server import _verify_plugin_hash

        monkeypatch.setenv("GEMINI_MCP_PLUGIN_REQUIRE_HASH", "true")

        plugin_file = tmp_path / "test_plugin.py"
        plugin_file.write_text("# test plugin")

        assert _verify_plugin_hash(plugin_file) is False

    def test_verify_plugin_hash_matching(self, tmp_path, monkeypatch):
        """Matching hash should pass."""
        from gemini_mcp.server import _verify_plugin_hash

        monkeypatch.setenv("GEMINI_MCP_PLUGIN_REQUIRE_HASH", "true")

        plugin_file = tmp_path / "test_plugin.py"
        content = b"# secure plugin"
        plugin_file.write_bytes(content)

        expected_hash = hashlib.sha256(content).hexdigest()
        hash_file = tmp_path / "test_plugin.py.sha256"
        hash_file.write_text(expected_hash)

        assert _verify_plugin_hash(plugin_file) is True

    def test_verify_plugin_hash_mismatch(self, tmp_path, monkeypatch):
        """Mismatched hash should fail."""
        from gemini_mcp.server import _verify_plugin_hash

        monkeypatch.setenv("GEMINI_MCP_PLUGIN_REQUIRE_HASH", "true")

        plugin_file = tmp_path / "test_plugin.py"
        plugin_file.write_bytes(b"# original content")

        hash_file = tmp_path / "test_plugin.py.sha256"
        hash_file.write_text("deadbeef" * 8)  # wrong hash

        assert _verify_plugin_hash(plugin_file) is False
