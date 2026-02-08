"""Swarm tools for multi-agent missions."""

import logging
from typing import Literal

from ..config import config

logger = logging.getLogger(__name__)


async def swarm_execute(
    objective: str,
    mode: Literal["fast", "thorough", "consensus", "async"] = "fast",
    agents: list[str] | None = None,
    context: str = "",
) -> dict:
    """
    Execute multi-agent missions.

    Args:
        objective: What to accomplish
        mode: Execution mode
        agents: Optional agent types
        context: Additional context

    Returns:
        Mission results
    """
    from ..swarm.core import SwarmOrchestrator
    from ..swarm.types import AgentType, ExecutionMode

    orchestrator = SwarmOrchestrator()

    # Map mode to execution settings
    if mode == "async":
        exec_mode = ExecutionMode.ASYNC
        agent_types = [AgentType.ARCHITECT]
    elif mode == "thorough":
        exec_mode = ExecutionMode.SYNC
        agent_types = [AgentType.ARCHITECT, AgentType.CODER, AgentType.REVIEWER]
    elif mode == "consensus":
        exec_mode = ExecutionMode.SYNC
        agent_types = [AgentType.ARCHITECT, AgentType.ANALYST, AgentType.REVIEWER]
    else:  # fast (default)
        exec_mode = ExecutionMode.SYNC
        agent_types = [AgentType.ARCHITECT]

    # Override with user-specified agents
    if agents:
        agent_types = []
        for a in agents:
            try:
                agent_types.append(AgentType(a.lower()))
            except ValueError:
                return {"error": f"Unknown agent: {a}"}

    result = await orchestrator.execute_mission(
        objective=objective,
        mode=exec_mode,
        agents=agent_types,
        context=context,
    )

    response = {
        "trace_id": result.trace_id,
        "status": (
            result.status.value
            if hasattr(result.status, "value")
            else str(result.status)
        ),
        "result": result.result,
        "error": result.error,
        "agents_used": [
            a.value if hasattr(a, "value") else str(a) for a in result.agents_used
        ],
        "tasks_completed": result.tasks_completed,
        "elapsed_seconds": result.elapsed_seconds,
    }

    if exec_mode == ExecutionMode.ASYNC:
        response["info"] = (
            f"Mission started. Use swarm_status(trace_id='{result.trace_id}') to check progress."
        )

    return response


async def swarm_adjudicate(
    query: str,
    panel: list[str] | None = None,
    strategy: Literal["unanimous", "majority", "supreme_court"] = "supreme_court",
) -> dict:
    """
    Convene expert panel for consensus.

    Args:
        query: Question requiring consensus
        panel: Expert personas
        strategy: Consensus strategy

    Returns:
        Panel verdict
    """
    from ..swarm.core import SwarmOrchestrator
    from ..swarm.types import AdjudicationStrategy

    orchestrator = SwarmOrchestrator()

    strategy_map = {
        "unanimous": AdjudicationStrategy.UNANIMOUS,
        "majority": AdjudicationStrategy.MAJORITY,
        "supreme_court": AdjudicationStrategy.SUPREME_COURT,
    }

    result = await orchestrator.adjudicate(
        query=query,
        panel_personas=panel,
        strategy=strategy_map.get(strategy, AdjudicationStrategy.SUPREME_COURT),
    )

    return {
        "trace_id": result.trace_id,
        "query": result.query,
        "verdict": result.verdict,
        "reasoning": result.reasoning,
        "confidence": result.confidence,
        "panel_size": len(result.panel_votes),
        "dissenting_opinions": result.dissenting_opinions,
        "elapsed_seconds": result.elapsed_seconds,
    }


async def swarm_status(
    trace_id: str | None = None,
    action: Literal["status", "results", "cancel", "trace", "list"] = "status",
) -> dict:
    """
    Check or manage swarm operations.

    Args:
        trace_id: Swarm trace ID
        action: What to do

    Returns:
        Status information
    """
    from ..swarm.core import SwarmOrchestrator
    from ..swarm.memory import get_trace_store, get_swarm_registry

    orchestrator = SwarmOrchestrator()
    store = get_trace_store()
    registry = get_swarm_registry()

    if action == "list":
        running = registry.list_running()
        recent = store.list_recent(limit=10)
        return {
            "action": "list",
            "running": running,
            "recent": recent,
        }

    if not trace_id:
        return {"error": "trace_id required for actions other than 'list'"}

    if action == "cancel":
        success = await orchestrator.cancel(trace_id)
        return {"action": "cancel", "trace_id": trace_id, "success": success}

    if action == "trace":
        trace = await orchestrator.get_trace(trace_id)
        if trace:
            return {
                "action": "trace",
                "trace_id": trace_id,
                "objective": trace.objective,
                "status": trace.status.value,
                "agents_used": [a.value for a in trace.agents_used],
                "result": trace.result,
            }
        return {"action": "trace", "error": "Trace not found"}

    # Default: status
    status = await orchestrator.get_status(trace_id)
    if status:
        return {"action": "status", **status}

    return {"action": "status", "error": "Swarm not found"}
