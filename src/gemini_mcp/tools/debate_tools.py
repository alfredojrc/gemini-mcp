"""Debate tools for AI-to-AI discussions."""

import logging
from typing import Literal

logger = logging.getLogger(__name__)


async def debate(
    topic: str,
    action: Literal["start", "list", "stats", "search", "load", "context"] = "start",
    strategy: str = "collaborative",
    context: str = "",
    debate_id: str | None = None,
) -> dict:
    """
    AI-to-AI debate system with memory persistence.

    Args:
        topic: Debate topic or search query
        action: What to do
        strategy: Debate strategy for 'start' action
        context: Additional context
        debate_id: Debate ID for 'load' action

    Returns:
        Debate results
    """
    from ..config import config
    from ..debate.orchestrator import DebateConfig, DebateOrchestrator, DebateStrategy

    # Input length validation — prevent memory exhaustion in TF-IDF tokenization
    max_input_chars = config.max_context_tokens * 4  # ~4 chars per token
    for name, value in [("topic", topic), ("context", context)]:
        if len(value) > max_input_chars:
            return {
                "action": action,
                "error": f"'{name}' too long ({len(value):,} chars). Maximum: {max_input_chars:,}",
            }

    orchestrator = DebateOrchestrator()

    if action == "list":
        debates = orchestrator.memory.get_all_debates(limit=20)
        return {
            "action": "list",
            "total": len(debates),
            "debates": [
                {
                    "debate_id": d["debate_id"],
                    "topic": d["topic"],
                    "timestamp": d["timestamp"],
                    "converged": d.get("converged", False),
                }
                for d in debates
            ],
        }

    if action == "stats":
        stats = orchestrator.memory.get_statistics()
        return {
            "action": "stats",
            "total_debates": stats["total_debates"],
            "total_insights": stats["total_insights"],
            "convergence_rate": f"{stats['convergence_rate']:.1%}",
        }

    if action == "search":
        related = orchestrator.memory.find_related_debates(topic, limit=5)
        return {
            "action": "search",
            "query": topic,
            "results": [
                {
                    "debate_id": r.debate_id,
                    "topic": r.topic,
                    "relevance": round(r.relevance_score, 2),
                    "key_insights": r.key_insights[:3],
                }
                for r in related
            ],
        }

    if action == "load" and debate_id:
        # Validate debate_id format (8-char hex from uuid4)
        if not debate_id.replace("-", "").isalnum() or len(debate_id) > 36:
            return {"action": "load", "error": f"Invalid debate_id format: {debate_id}"}
        result = await orchestrator.load_debate(debate_id)
        if result:
            return {
                "action": "load",
                "debate_id": result.debate_id,
                "topic": result.topic,
                "synthesis": result.final_synthesis,
                "consensus": result.consensus_points,
            }
        return {"action": "load", "error": "Debate not found"}

    if action == "context":
        context_summary = orchestrator.memory.get_context_summary(topic, max_tokens=2000)
        return {
            "action": "context",
            "topic": topic,
            "context_summary": context_summary or "No related debates found.",
        }

    # Default: start new debate
    strategy_map = {
        "adversarial": DebateStrategy.ADVERSARIAL,
        "collaborative": DebateStrategy.COLLABORATIVE,
        "socratic": DebateStrategy.SOCRATIC,
        "devil_advocate": DebateStrategy.DEVIL_ADVOCATE,
    }

    resolved = strategy_map.get(strategy.lower())
    if resolved is None:
        valid = ", ".join(sorted(strategy_map.keys()))
        logger.warning(f"Unknown debate strategy '{strategy}', defaulting to collaborative")
        return {
            "action": "start",
            "error": f"Unknown strategy '{strategy}'. Valid strategies: {valid}",
        }

    debate_config = DebateConfig(
        topic=topic,
        strategy=resolved,
        max_rounds=5,
        context=context,
    )

    result = await orchestrator.start_debate(debate_config)

    return {
        "action": "start",
        "debate_id": result.debate_id,
        "topic": result.topic,
        "rounds_completed": result.rounds_completed,
        "converged": result.converged,
        "consensus": result.consensus_points,
        "synthesis": result.final_synthesis,
        "actions": result.actionable_items,
    }
