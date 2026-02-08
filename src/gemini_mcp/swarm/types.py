"""Type definitions for the Swarm system."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class AgentType(StrEnum):
    """Available agent types."""

    ARCHITECT = "architect"
    RESEARCHER = "researcher"
    CODER = "coder"
    ANALYST = "analyst"
    REVIEWER = "reviewer"
    TESTER = "tester"
    DOCUMENTER = "documenter"


class ExecutionMode(StrEnum):
    """Swarm execution modes."""

    SYNC = "sync"  # Synchronous execution
    ASYNC = "async"  # Asynchronous (fire-and-forget)


class TaskStatus(StrEnum):
    """Task status values."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AdjudicationStrategy(StrEnum):
    """Strategies for reaching consensus."""

    UNANIMOUS = "unanimous"  # All must agree
    MAJORITY = "majority"  # Simple majority
    SUPREME_COURT = "supreme_court"  # Judge synthesizes


@dataclass
class SwarmResult:
    """Result of a swarm mission."""

    trace_id: str
    status: TaskStatus
    result: str | None = None
    error: str | None = None
    agents_used: list[AgentType] = field(default_factory=list)
    tasks_completed: int = 0
    total_turns: int = 0
    elapsed_seconds: float = 0.0


@dataclass
class PanelVote:
    """Vote from an expert panel member."""

    agent_type: AgentType
    position: str
    reasoning: str
    confidence: float
    dissent: bool = False


@dataclass
class AdjudicationResult:
    """Result of an expert panel adjudication."""

    trace_id: str
    query: str
    verdict: str
    reasoning: str
    confidence: float
    panel_votes: list[PanelVote] = field(default_factory=list)
    dissenting_opinions: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0


@dataclass
class SwarmMessage:
    """Message in a swarm conversation."""

    role: str  # user, assistant, system
    content: str
    agent_type: AgentType | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    tool_calls: list[dict] = field(default_factory=list)


@dataclass
class ExecutionTrace:
    """Full trace of a swarm execution."""

    trace_id: str
    objective: str
    status: TaskStatus
    agents_used: list[AgentType] = field(default_factory=list)
    messages: list[SwarmMessage] = field(default_factory=list)
    result: str | None = None
    error: str | None = None
    total_turns: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
