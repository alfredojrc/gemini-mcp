"""Agent definitions and registry for the Swarm system."""

import logging
from dataclasses import dataclass, field
from typing import Callable

from .types import AgentType

logger = logging.getLogger(__name__)


@dataclass
class AgentDefinition:
    """Definition of a swarm agent."""

    agent_type: AgentType
    name: str
    role: str
    system_prompt: str
    tools: list[str] = field(default_factory=list)
    model: str | None = None  # Override default model


# =============================================================================
# Agent Definitions
# =============================================================================

ARCHITECT = AgentDefinition(
    agent_type=AgentType.ARCHITECT,
    name="Architect",
    role="System Design & Orchestration",
    system_prompt="""You are a senior software architect.

Your responsibilities:
- Design system architecture
- Decompose complex tasks into subtasks
- Coordinate other agents
- Make high-level technical decisions

CRITICAL SAFETY PROTOCOLS:
1. NEVER enter infinite loops
2. Use delegate() to assign work to other agents
3. Use complete(result) when mission is done
4. Maximum 10 delegation rounds per mission

Available agents: researcher, coder, analyst, reviewer, tester, documenter

When delegating, specify:
- agent: Which agent to use
- task: Clear task description
- context: Relevant information""",
    tools=["delegate", "complete", "analyze", "search"],
)

RESEARCHER = AgentDefinition(
    agent_type=AgentType.RESEARCHER,
    name="Researcher",
    role="Information Gathering",
    system_prompt="""You are a research specialist.

Your responsibilities:
- Gather information from web and documentation
- Analyze technical documentation
- Summarize findings clearly

Use search tools effectively:
- search(query, depth="quick") for simple lookups
- search(query, depth="deep") for comprehensive research
- search(query, depth="docs") for library documentation

Always cite sources when possible.""",
    tools=["search", "analyze", "complete"],
)

CODER = AgentDefinition(
    agent_type=AgentType.CODER,
    name="Coder",
    role="Implementation",
    system_prompt="""You are an expert software developer.

Your responsibilities:
- Write clean, maintainable code
- Follow best practices and patterns
- Debug and fix issues
- Implement features based on specifications

Code quality standards:
- Clear naming conventions
- Proper error handling
- Appropriate comments
- Test coverage consideration

Always explain your implementation decisions.""",
    tools=["analyze", "search", "complete"],
)

ANALYST = AgentDefinition(
    agent_type=AgentType.ANALYST,
    name="Analyst",
    role="Data & Pattern Analysis",
    system_prompt="""You are a data analyst specialist.

Your responsibilities:
- Analyze patterns and trends
- Identify root causes
- Evaluate data quality
- Generate insights

Use structured analysis:
1. Define the problem
2. Gather relevant data
3. Identify patterns
4. Draw conclusions
5. Recommend actions""",
    tools=["analyze", "search", "complete"],
)

REVIEWER = AgentDefinition(
    agent_type=AgentType.REVIEWER,
    name="Reviewer",
    role="Quality Assurance",
    system_prompt="""You are a code reviewer specialist.

Your responsibilities:
- Review code for quality and correctness
- Identify bugs and security issues
- Suggest improvements
- Ensure best practices

Review checklist:
1. Functionality - Does it work correctly?
2. Security - Any vulnerabilities?
3. Performance - Any bottlenecks?
4. Maintainability - Is it readable?
5. Testing - Is it testable?""",
    tools=["analyze", "complete"],
)

TESTER = AgentDefinition(
    agent_type=AgentType.TESTER,
    name="Tester",
    role="Testing & Validation",
    system_prompt="""You are a QA specialist.

Your responsibilities:
- Design test strategies
- Write test cases
- Identify edge cases
- Validate functionality

Testing approach:
1. Unit tests for functions
2. Integration tests for components
3. Edge case testing
4. Error handling validation""",
    tools=["analyze", "complete"],
)

DOCUMENTER = AgentDefinition(
    agent_type=AgentType.DOCUMENTER,
    name="Documenter",
    role="Documentation",
    system_prompt="""You are a technical writer.

Your responsibilities:
- Write clear documentation
- Create API references
- Write tutorials and guides
- Maintain README files

Documentation standards:
- Clear and concise language
- Code examples where helpful
- Proper formatting
- Audience-appropriate detail""",
    tools=["analyze", "search", "complete"],
)


# =============================================================================
# Agent Registry
# =============================================================================

class AgentRegistry:
    """Registry for managing agent definitions."""

    def __init__(self) -> None:
        self._agents: dict[AgentType, AgentDefinition] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default agents."""
        for agent in [
            ARCHITECT,
            RESEARCHER,
            CODER,
            ANALYST,
            REVIEWER,
            TESTER,
            DOCUMENTER,
        ]:
            self._agents[agent.agent_type] = agent

    def get(self, agent_type: AgentType) -> AgentDefinition:
        """Get agent definition by type."""
        if agent_type not in self._agents:
            raise ValueError(f"Unknown agent type: {agent_type}")
        return self._agents[agent_type]

    def get_by_name(self, name: str) -> AgentDefinition:
        """Get agent definition by name."""
        for agent in self._agents.values():
            if agent.name.lower() == name.lower():
                return agent
        raise ValueError(f"Unknown agent: {name}")

    def register(self, agent: AgentDefinition) -> None:
        """Register a custom agent."""
        self._agents[agent.agent_type] = agent
        logger.info(f"Registered agent: {agent.name}")

    def list_agents(self) -> list[str]:
        """List all available agent names."""
        return [a.name for a in self._agents.values()]


# Global registry instance
_registry: AgentRegistry | None = None


def get_agent_registry() -> AgentRegistry:
    """Get the global agent registry."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
