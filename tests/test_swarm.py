"""Tests for the swarm orchestrator."""

import pytest

from gemini_mcp.swarm.core import SwarmOrchestrator
from gemini_mcp.swarm.memory import AsyncBlackboard, SwarmRegistry, TraceStore
from gemini_mcp.swarm.types import (
    AgentType,
    ExecutionTrace,
    TaskStatus,
)


class TestSwarmParsing:
    """Tests for architect output parsing (no API calls needed)."""

    def setup_method(self):
        self.orch = SwarmOrchestrator.__new__(SwarmOrchestrator)
        # Provide a minimal registry for prompt-building tests
        from gemini_mcp.swarm.agents import AgentRegistry

        self.orch.registry = AgentRegistry()

    def test_parse_single_delegation(self):
        """Parse a single delegate() call."""
        text = 'I need more info. delegate("researcher", "find papers on ML trading")'
        result = self.orch._parse_delegations(text)
        assert len(result) == 1
        assert result[0][0] == "researcher"
        assert "papers" in result[0][1]

    def test_parse_multiple_delegations(self):
        """Parse multiple delegate() calls."""
        text = (
            'delegate("coder", "implement the API endpoint")\n'
            'delegate("tester", "write unit tests for the endpoint")'
        )
        result = self.orch._parse_delegations(text)
        assert len(result) == 2
        assert result[0][0] == "coder"
        assert result[1][0] == "tester"

    def test_parse_delegation_no_quotes(self):
        """Parse delegate() without quotes around agent name."""
        text = "delegate(analyst, analyze the data patterns)"
        result = self.orch._parse_delegations(text)
        assert len(result) == 1
        assert result[0][0] == "analyst"

    def test_parse_no_delegation(self):
        """No delegate() calls should return empty list."""
        text = "I can answer this directly. The solution is..."
        result = self.orch._parse_delegations(text)
        assert result == []

    def test_parse_completion(self):
        """Parse complete() with result."""
        text = 'complete("The API should use REST with JWT auth")'
        result = self.orch._parse_completion(text)
        assert result is not None
        assert "REST" in result
        assert "JWT" in result

    def test_parse_completion_multiline(self):
        """Parse complete() spanning multiple lines."""
        text = 'complete("Line one.\nLine two.\nLine three.")'
        result = self.orch._parse_completion(text)
        assert result is not None
        assert "Line one" in result

    def test_parse_no_completion(self):
        """No complete() should return None."""
        text = "Let me delegate some tasks first."
        result = self.orch._parse_completion(text)
        assert result is None

    def test_build_architect_prompt_basic(self):
        """Build a basic architect prompt."""
        prompt = self.orch._build_architect_prompt(
            objective="Design an API",
            context="",
            agent_results={},
            turn=1,
            max_turns=10,
        )
        assert "Design an API" in prompt
        assert "Turn 1/10" in prompt
        assert "delegate(" in prompt
        assert "complete(" in prompt

    def test_build_architect_prompt_with_results(self):
        """Build prompt including prior agent results."""
        prompt = self.orch._build_architect_prompt(
            objective="Build a feature",
            context="Use Python",
            agent_results={"researcher": "Found 3 relevant papers"},
            turn=2,
            max_turns=5,
        )
        assert "researcher" in prompt
        assert "Found 3 relevant papers" in prompt
        assert "Use Python" in prompt


class TestPersonaLoader:
    """Tests for custom persona loading from markdown files."""

    def test_load_persona_from_file(self, tmp_path):
        """Load a persona from a markdown file."""
        from gemini_mcp.swarm.agents import AgentRegistry

        persona_file = tmp_path / "test_expert.md"
        persona_file.write_text(
            "# Test Expert\n\n"
            "## Role\nA test specialist.\n\n"
            "## Expertise\n- Testing\n- Validation\n\n"
            "## Tools\n- analyze\n- search\n- complete\n\n"
            "## Guidelines\n1. Be thorough\n"
        )

        registry = AgentRegistry()
        count = registry.load_personas_from_dir(tmp_path)
        assert count == 1
        assert registry.has_custom("test_expert")

        agent = registry.get_by_name("test_expert")
        assert agent.name == "Test Expert"
        assert "test specialist" in agent.system_prompt
        assert "analyze" in agent.tools

    def test_load_skips_readme(self, tmp_path):
        """README.md should be skipped."""
        from gemini_mcp.swarm.agents import AgentRegistry

        (tmp_path / "README.md").write_text("# Not a persona")
        registry = AgentRegistry()
        count = registry.load_personas_from_dir(tmp_path)
        assert count == 0

    def test_load_nonexistent_dir(self):
        """Non-existent directory returns 0."""
        from gemini_mcp.swarm.agents import AgentRegistry

        registry = AgentRegistry()
        count = registry.load_personas_from_dir("/nonexistent/path")
        assert count == 0

    def test_custom_personas_listed_in_prompt(self, tmp_path):
        """Custom personas should appear in the architect prompt."""
        from gemini_mcp.swarm.agents import AgentRegistry

        persona_file = tmp_path / "my_specialist.md"
        persona_file.write_text("# My Specialist\n\n## Role\nDoes stuff.\n")

        registry = AgentRegistry()
        registry.load_personas_from_dir(tmp_path)

        # Verify the custom agent shows up in list
        all_agents = registry.list_agents()
        assert "My Specialist" in all_agents
        custom = registry.list_custom_agents()
        assert "My Specialist" in custom


class TestTraceStore:
    """Tests for TraceStore persistence with file locking."""

    def test_save_and_load(self, tmp_path, monkeypatch):
        """Save and load a trace."""
        monkeypatch.setenv("GEMINI_MCP_DATA_DIR", str(tmp_path))
        from gemini_mcp.config import GeminiMCPConfig

        monkeypatch.setattr("gemini_mcp.swarm.memory.config", GeminiMCPConfig())

        store = TraceStore()
        trace = ExecutionTrace(
            trace_id="test-123",
            objective="Test mission",
            status=TaskStatus.COMPLETED,
            agents_used=[AgentType.ARCHITECT, AgentType.CODER],
            result="Success",
            total_turns=3,
        )
        store.save(trace)

        loaded = store.load("test-123")
        assert loaded is not None
        assert loaded.trace_id == "test-123"
        assert loaded.objective == "Test mission"
        assert loaded.status == TaskStatus.COMPLETED
        assert loaded.result == "Success"
        assert loaded.total_turns == 3
        assert AgentType.ARCHITECT in loaded.agents_used

    def test_load_nonexistent(self, tmp_path, monkeypatch):
        """Loading a nonexistent trace returns None."""
        monkeypatch.setenv("GEMINI_MCP_DATA_DIR", str(tmp_path))
        from gemini_mcp.config import GeminiMCPConfig

        monkeypatch.setattr("gemini_mcp.swarm.memory.config", GeminiMCPConfig())

        store = TraceStore()
        assert store.load("nonexistent") is None

    def test_list_recent(self, tmp_path, monkeypatch):
        """List recent traces."""
        monkeypatch.setenv("GEMINI_MCP_DATA_DIR", str(tmp_path))
        from gemini_mcp.config import GeminiMCPConfig

        monkeypatch.setattr("gemini_mcp.swarm.memory.config", GeminiMCPConfig())

        store = TraceStore()
        for i in range(5):
            trace = ExecutionTrace(
                trace_id=f"trace-{i}",
                objective=f"Mission {i}",
                status=TaskStatus.COMPLETED,
                agents_used=[AgentType.ARCHITECT],
            )
            store.save(trace)

        recent = store.list_recent(limit=3)
        assert len(recent) == 3

    def test_lock_sidecar_created(self, tmp_path, monkeypatch):
        """Saving a trace creates a .lock sidecar file."""
        monkeypatch.setenv("GEMINI_MCP_DATA_DIR", str(tmp_path))
        from gemini_mcp.config import GeminiMCPConfig

        monkeypatch.setattr("gemini_mcp.swarm.memory.config", GeminiMCPConfig())

        store = TraceStore()
        trace = ExecutionTrace(
            trace_id="lock-test",
            objective="Test locking",
            status=TaskStatus.COMPLETED,
            agents_used=[AgentType.ARCHITECT],
        )
        store.save(trace)

        lock_file = store.storage_dir / "lock-test.json.lock"
        assert lock_file.exists()


class TestSwarmRegistry:
    """Tests for in-memory swarm registry."""

    @pytest.mark.asyncio
    async def test_register_and_check(self):
        """Register a swarm and check status."""
        reg = SwarmRegistry()
        await reg.register("test-1", "Mission A")
        assert reg.is_running("test-1")
        assert not reg.is_running("nonexistent")

    @pytest.mark.asyncio
    async def test_unregister(self):
        """Unregister removes from running list."""
        reg = SwarmRegistry()
        await reg.register("test-2", "Mission B")
        await reg.unregister("test-2")
        assert not reg.is_running("test-2")

    @pytest.mark.asyncio
    async def test_list_running(self):
        """List running swarms."""
        reg = SwarmRegistry()
        await reg.register("a", "Mission A")
        await reg.register("b", "Mission B")
        running = reg.list_running()
        assert len(running) == 2

    @pytest.mark.asyncio
    async def test_update_status(self):
        """Update swarm status."""
        reg = SwarmRegistry()
        await reg.register("s1", "Mission")
        await reg.update_status("s1", "paused")
        running = reg.list_running()
        assert running[0]["status"] == "paused"


class TestAsyncBlackboard:
    """Tests for shared blackboard memory."""

    @pytest.mark.asyncio
    async def test_write_and_read(self):
        """Write and read values."""
        bb = AsyncBlackboard()
        await bb.write("key1", {"data": 42})
        result = await bb.read("key1")
        assert result == {"data": 42}

    @pytest.mark.asyncio
    async def test_read_nonexistent(self):
        """Reading nonexistent key returns None."""
        bb = AsyncBlackboard()
        assert await bb.read("missing") is None

    @pytest.mark.asyncio
    async def test_list_keys(self):
        """List all keys."""
        bb = AsyncBlackboard()
        await bb.write("a", 1)
        await bb.write("b", 2)
        keys = await bb.list_keys()
        assert set(keys) == {"a", "b"}

    @pytest.mark.asyncio
    async def test_clear(self):
        """Clear removes all entries."""
        bb = AsyncBlackboard()
        await bb.write("x", 1)
        await bb.clear()
        assert await bb.list_keys() == []
