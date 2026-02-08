"""Debate orchestrator for AI-to-AI discussions."""

import json
import logging
import math
import re
import time
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from ..config import config
from ..core.gemini import GeminiRequest, get_client

logger = logging.getLogger(__name__)


class DebateStrategy(StrEnum):
    """Debate strategies."""

    COLLABORATIVE = "collaborative"
    ADVERSARIAL = "adversarial"
    SOCRATIC = "socratic"
    DEVIL_ADVOCATE = "devil_advocate"


@dataclass
class DebateConfig:
    """Configuration for a debate."""

    topic: str
    strategy: DebateStrategy = DebateStrategy.COLLABORATIVE
    max_rounds: int = 5
    min_rounds: int = 3
    context: str = ""


@dataclass
class DebateRound:
    """A single round of debate."""

    round_number: int
    expert_a_response: str = ""
    expert_b_response: str = ""
    novelty_score: float = 0.0


@dataclass
class DebateResult:
    """Result of a completed debate."""

    debate_id: str
    topic: str
    strategy: DebateStrategy
    rounds_completed: int
    rounds: list[DebateRound] = field(default_factory=list)
    final_synthesis: str = ""
    consensus_points: list[str] = field(default_factory=list)
    disagreement_points: list[str] = field(default_factory=list)
    actionable_items: list[str] = field(default_factory=list)
    converged: bool = False
    elapsed_seconds: float = 0.0


@dataclass
class RelatedDebate:
    """Reference to a related past debate."""

    debate_id: str
    topic: str
    relevance_score: float
    key_insights: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Disk-quota constants
# ---------------------------------------------------------------------------
_MAX_DEBATE_FILES = 500  # prune oldest when exceeded


class DebateMemory:
    """Persistent memory for debates with disk-quota enforcement."""

    def __init__(self) -> None:
        self.storage_dir = config.debate_storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save(self, result: DebateResult) -> None:
        """Save debate to disk, enforcing disk quota."""
        debate_file = self.storage_dir / f"{result.debate_id}.json"
        data = {
            "debate_id": result.debate_id,
            "topic": result.topic,
            "strategy": result.strategy.value,
            "rounds_completed": result.rounds_completed,
            "synthesis": result.final_synthesis,
            "consensus": result.consensus_points,
            "disagreements": result.disagreement_points,
            "actions": result.actionable_items,
            "converged": result.converged,
            "timestamp": datetime.now().isoformat(),
        }
        debate_file.write_text(json.dumps(data, indent=2))
        self._enforce_quota()

    def _enforce_quota(self) -> None:
        """Remove oldest debate files when over quota."""
        files = sorted(self.storage_dir.glob("*.json"), key=lambda f: f.stat().st_mtime)
        while len(files) > _MAX_DEBATE_FILES:
            oldest = files.pop(0)
            oldest.unlink(missing_ok=True)
            logger.debug(f"Pruned old debate: {oldest.name}")

    def load(self, debate_id: str) -> DebateResult | None:
        """Load debate from disk."""
        debate_file = self.storage_dir / f"{debate_id}.json"
        if not debate_file.exists():
            return None

        try:
            data = json.loads(debate_file.read_text())
            return DebateResult(
                debate_id=data["debate_id"],
                topic=data["topic"],
                strategy=DebateStrategy(data["strategy"]),
                rounds_completed=data["rounds_completed"],
                final_synthesis=data.get("synthesis", ""),
                consensus_points=data.get("consensus", []),
                disagreement_points=data.get("disagreements", []),
                actionable_items=data.get("actions", []),
                converged=data.get("converged", False),
            )
        except Exception as e:
            logger.error(f"Failed to load debate {debate_id}: {e}")
            return None

    def get_all_debates(self, limit: int = 20) -> list[dict]:
        """Get all debates."""
        debates = []
        for debate_file in sorted(
            self.storage_dir.glob("*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )[:limit]:
            try:
                data = json.loads(debate_file.read_text())
                debates.append(data)
            except Exception:
                pass
        return debates

    def find_related_debates(self, topic: str, limit: int = 5) -> list[RelatedDebate]:
        """Find debates related to a topic using TF-IDF cosine similarity."""
        related = []
        topic_tfidf = _tfidf_vector(topic)

        for debate_file in self.storage_dir.glob("*.json"):
            try:
                data = json.loads(debate_file.read_text())
                debate_tfidf = _tfidf_vector(data["topic"])
                score = _cosine_similarity(topic_tfidf, debate_tfidf)
                if score > 0.1:
                    related.append(
                        RelatedDebate(
                            debate_id=data["debate_id"],
                            topic=data["topic"],
                            relevance_score=score,
                            key_insights=data.get("consensus", [])[:3],
                        )
                    )
            except Exception:
                pass

        return sorted(related, key=lambda r: r.relevance_score, reverse=True)[:limit]

    def get_statistics(self) -> dict:
        """Get debate statistics."""
        debates = self.get_all_debates(limit=1000)
        total = len(debates)
        converged = sum(1 for d in debates if d.get("converged", False))
        insights = sum(len(d.get("consensus", [])) for d in debates)

        return {
            "total_debates": total,
            "total_insights": insights,
            "convergence_rate": converged / total if total > 0 else 0,
        }

    def get_context_summary(self, topic: str, max_tokens: int = 2000) -> str | None:
        """Get context summary from related debates."""
        related = self.find_related_debates(topic, limit=3)
        if not related:
            return None

        summaries = []
        for r in related:
            debate = self.load(r.debate_id)
            if debate:
                summaries.append(
                    f"Topic: {debate.topic}\n"
                    f"Key points: {', '.join(debate.consensus_points[:3])}"
                )

        result = "\n\n".join(summaries)
        if len(result) > max_tokens:
            logger.warning(f"Debate context truncated from {len(result)} to {max_tokens} chars")
        return result[:max_tokens]


# ---------------------------------------------------------------------------
# TF-IDF helpers for novelty & relevance (lightweight, no dependencies)
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + lowercase tokenizer with stopword removal."""
    stopwords = frozenset(
        {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "shall",
            "can",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "and",
            "but",
            "or",
            "nor",
            "not",
            "so",
            "yet",
            "both",
            "either",
            "neither",
            "it",
            "its",
            "this",
            "that",
            "these",
            "those",
            "i",
            "you",
            "he",
            "she",
            "we",
            "they",
            "me",
            "him",
            "her",
            "us",
            "them",
            "my",
            "your",
        }
    )
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w for w in words if w not in stopwords and len(w) > 1]


def _tfidf_vector(text: str) -> dict[str, float]:
    """Return a term-frequency vector (IDF not available without corpus)."""
    tokens = _tokenize(text)
    if not tokens:
        return {}
    counts = Counter(tokens)
    total = len(tokens)
    return {word: count / total for word, count in counts.items()}


def _cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity between two sparse TF vectors."""
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    if not common:
        return 0.0
    dot = sum(a[k] * b[k] for k in common)
    mag_a = math.sqrt(sum(v * v for v in a.values()))
    mag_b = math.sqrt(sum(v * v for v in b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


class DebateOrchestrator:
    """Orchestrator for AI-to-AI debates.

    Expert A uses the default (pro) model; Expert B uses the fast (flash)
    model with a higher temperature, ensuring genuinely distinct perspectives.
    """

    def __init__(self) -> None:
        self.memory = DebateMemory()
        self.client = get_client()

    async def start_debate(
        self,
        debate_cfg: DebateConfig,
        progress_callback: Callable[[float, str], Awaitable[None]] | None = None,
    ) -> DebateResult:
        """Start a new debate."""
        debate_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        rounds: list[DebateRound] = []

        # Get related context
        context = self.memory.get_context_summary(debate_cfg.topic)

        # Strategy-specific prompts
        strategy_prompts = {
            DebateStrategy.COLLABORATIVE: "Work together to find the best solution.",
            DebateStrategy.ADVERSARIAL: "Challenge each other's positions rigorously.",
            DebateStrategy.SOCRATIC: "Use questions to explore the topic deeply.",
            DebateStrategy.DEVIL_ADVOCATE: "One expert should challenge assumptions.",
        }

        strategy_instruction = strategy_prompts.get(
            debate_cfg.strategy, strategy_prompts[DebateStrategy.COLLABORATIVE]
        )

        # Run debate rounds
        previous_responses: list[tuple[str, str]] = []

        for round_num in range(1, debate_cfg.max_rounds + 1):
            if progress_callback:
                progress = round_num / (debate_cfg.max_rounds + 1)
                await progress_callback(progress, f"Round {round_num}...")

            # Expert A — default/pro model, lower temperature
            expert_a_prompt = self._build_expert_prompt(
                "Expert A",
                debate_cfg.topic,
                strategy_instruction,
                context,
                debate_cfg.context,
                previous_responses,
                round_num,
            )
            response_a = await self._get_expert_response(
                expert_a_prompt,
                model=self.client.default_model,
                temperature=0.7,
            )

            # Expert B — fast/flash model, higher temperature
            previous_responses.append(("Expert A", response_a))
            expert_b_prompt = self._build_expert_prompt(
                "Expert B",
                debate_cfg.topic,
                strategy_instruction,
                context,
                debate_cfg.context,
                previous_responses,
                round_num,
            )
            response_b = await self._get_expert_response(
                expert_b_prompt,
                model=self.client.fast_model,
                temperature=1.0,
            )
            previous_responses.append(("Expert B", response_b))

            # Calculate novelty using TF-IDF cosine similarity
            novelty = self._calculate_novelty(response_a, response_b, rounds)

            rounds.append(
                DebateRound(
                    round_number=round_num,
                    expert_a_response=response_a,
                    expert_b_response=response_b,
                    novelty_score=novelty,
                )
            )

            # Check for convergence using config threshold
            if round_num >= debate_cfg.min_rounds and novelty < config.debate_novelty_threshold:
                break

        # Generate synthesis
        if progress_callback:
            await progress_callback(0.9, "Generating synthesis...")

        synthesis = await self._generate_synthesis(debate_cfg.topic, rounds)

        result = DebateResult(
            debate_id=debate_id,
            topic=debate_cfg.topic,
            strategy=debate_cfg.strategy,
            rounds_completed=len(rounds),
            rounds=rounds,
            final_synthesis=synthesis["synthesis"],
            consensus_points=synthesis.get("consensus", []),
            disagreement_points=synthesis.get("disagreements", []),
            actionable_items=synthesis.get("actions", []),
            converged=len(rounds) < debate_cfg.max_rounds,
            elapsed_seconds=time.time() - start_time,
        )

        self.memory.save(result)
        return result

    async def load_debate(self, debate_id: str) -> DebateResult | None:
        """Load a previous debate."""
        return self.memory.load(debate_id)

    def _build_expert_prompt(
        self,
        expert_name: str,
        topic: str,
        strategy: str,
        related_context: str | None,
        user_context: str,
        previous: list[tuple[str, str]],
        round_num: int,
    ) -> str:
        """Build prompt for an expert turn."""
        prompt = f"""You are {expert_name} in a structured debate.

Topic: {topic}
Strategy: {strategy}
Round: {round_num}

{f"Related past discussions: {related_context}" if related_context else ""}
{f"Additional context: {user_context}" if user_context else ""}

"""
        if previous:
            prompt += "Previous responses:\n"
            for name, response in previous[-4:]:
                prompt += f"\n{name}: {response[:500]}...\n"

        prompt += (
            f"\nProvide your perspective as {expert_name}. Be substantive and address key points."
        )

        return prompt

    async def _get_expert_response(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.8,
    ) -> str:
        """Get response from an expert using a specific model/temperature."""
        request = GeminiRequest(
            prompt=prompt,
            model=model or self.client.default_model,
            timeout=config.debate_turn_timeout,
            temperature=temperature,
        )
        response = await self.client.generate(request)
        return response.text

    def _calculate_novelty(
        self, response_a: str, response_b: str, previous_rounds: list[DebateRound]
    ) -> float:
        """Calculate novelty via TF-IDF cosine similarity.

        Compares the current round's content against previous rounds.
        High similarity (>0.8) → low novelty → convergence.
        """
        if not previous_rounds:
            return 1.0

        # Build TF vectors for current round and previous rounds
        current_text = response_a + " " + response_b
        current_vec = _tfidf_vector(current_text)

        prev_text = " ".join(
            r.expert_a_response + " " + r.expert_b_response for r in previous_rounds[-2:]
        )
        prev_vec = _tfidf_vector(prev_text)

        similarity = _cosine_similarity(current_vec, prev_vec)
        # Novelty = 1 - similarity (high similarity = low novelty = convergence)
        return max(0.0, min(1.0, 1.0 - similarity))

    async def _generate_synthesis(self, topic: str, rounds: list[DebateRound]) -> dict:
        """Generate final synthesis of the debate."""
        rounds_summary = "\n".join(
            [
                f"Round {r.round_number}:\n"
                f"  Expert A: {r.expert_a_response[:300]}...\n"
                f"  Expert B: {r.expert_b_response[:300]}..."
                for r in rounds
            ]
        )

        prompt = f"""Synthesize this debate on: {topic}

{rounds_summary}

Respond with ONLY a JSON object (no markdown fences):
{{
  "synthesis": "Overall conclusion",
  "consensus": ["agreed point 1", "agreed point 2"],
  "disagreements": ["unresolved point 1"],
  "actions": ["recommended action 1"]
}}"""

        request = GeminiRequest(prompt=prompt, model=self.client.default_model)
        response = await self.client.generate(request)

        # Robust JSON extraction — try full text first, then bracket-balanced parse
        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            pass

        # Strip markdown code fences if present
        text = response.text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

        # Bracket-balanced extraction — find outermost { ... }
        parsed = self._extract_json_object(text)
        if parsed is not None:
            return parsed

        return {
            "synthesis": response.text,
            "consensus": [],
            "disagreements": [],
            "actions": [],
        }

    @staticmethod
    def _extract_json_object(text: str) -> dict | None:
        """Extract the first balanced JSON object from text.

        Uses bracket counting instead of greedy regex to handle nested
        braces and escaped quotes correctly.
        """
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False

        for i in range(start, len(text)):
            c = text[i]
            if escape:
                escape = False
                continue
            if c == "\\":
                escape = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        return None
        return None
