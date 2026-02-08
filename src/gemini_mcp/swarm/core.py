"""Swarm orchestrator for multi-agent missions."""

import asyncio
import json
import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime

from ..config import config
from ..core.gemini import GeminiRequest, get_client
from .agents import AgentDefinition, get_agent_registry
from .memory import (
    get_swarm_registry,
    get_trace_store,
)
from .types import (
    AdjudicationResult,
    AdjudicationStrategy,
    AgentType,
    ExecutionMode,
    ExecutionTrace,
    PanelVote,
    SwarmMessage,
    SwarmResult,
    TaskStatus,
)

logger = logging.getLogger(__name__)

# Maximum turns any single mission may take (hard ceiling).
_MAX_TURNS = 10


class SwarmOrchestrator:
    """Orchestrator for multi-agent swarm missions.

    Implements the Supervisor Pattern: the architect agent analyses the
    objective and may delegate sub-tasks to specialist agents.  Delegation
    is parsed from the architect's structured output and executed in an
    iterative loop with depth/turn limits.
    """

    def __init__(self) -> None:
        self.registry = get_agent_registry()
        self.trace_store = get_trace_store()
        self.swarm_registry = get_swarm_registry()
        self.client = get_client()
        self.max_depth = config.swarm_max_depth

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute_mission(
        self,
        objective: str,
        mode: ExecutionMode = ExecutionMode.SYNC,
        agents: list[AgentType] | None = None,
        context: str = "",
        progress_callback: Callable[[float, str], Awaitable[None]] | None = None,
    ) -> SwarmResult:
        """Execute a multi-agent mission."""
        trace_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        agents = agents or [AgentType.ARCHITECT]

        trace = ExecutionTrace(
            trace_id=trace_id,
            objective=objective,
            status=TaskStatus.IN_PROGRESS,
            agents_used=agents,
        )

        await self.swarm_registry.register(trace_id, objective)

        try:
            if mode == ExecutionMode.ASYNC:
                # Background execution — store result when done.
                asyncio.create_task(self._run_and_persist(trace, context, progress_callback))
                return SwarmResult(
                    trace_id=trace_id,
                    status=TaskStatus.IN_PROGRESS,
                    result="Mission started in background",
                    agents_used=agents,
                    elapsed_seconds=time.time() - start_time,
                )
            else:
                return await self._run_mission(trace, context, progress_callback)

        except Exception as e:
            logger.exception(f"Mission failed: {e}")
            trace.status = TaskStatus.FAILED
            trace.error = str(e)
            self.trace_store.save(trace)
            await self.swarm_registry.unregister(trace_id)

            return SwarmResult(
                trace_id=trace_id,
                status=TaskStatus.FAILED,
                error=str(e),
                agents_used=agents,
                elapsed_seconds=time.time() - start_time,
            )

    # ------------------------------------------------------------------
    # Async wrapper — persists result for background missions
    # ------------------------------------------------------------------

    async def _run_and_persist(
        self,
        trace: ExecutionTrace,
        context: str,
        progress_callback: Callable[[float, str], Awaitable[None]] | None,
    ) -> None:
        """Run mission in background and persist the result."""
        try:
            result = await self._run_mission(trace, context, progress_callback)
            # Result is already saved inside _run_mission, but log completion.
            logger.info(f"Background mission {trace.trace_id} completed: {result.status.value}")
        except Exception as e:
            logger.exception(f"Background mission {trace.trace_id} failed: {e}")
            trace.status = TaskStatus.FAILED
            trace.error = str(e)
            trace.completed_at = datetime.now()
            self.trace_store.save(trace)
        finally:
            # Ensure cleanup even on cancellation (CancelledError bypasses except Exception)
            if self.swarm_registry.is_running(trace.trace_id):
                await self.swarm_registry.unregister(trace.trace_id)

    # ------------------------------------------------------------------
    # Core mission loop — delegation + depth enforcement + timeout
    # ------------------------------------------------------------------

    async def _run_mission(
        self,
        trace: ExecutionTrace,
        context: str,
        progress_callback: Callable[[float, str], Awaitable[None]] | None = None,
    ) -> SwarmResult:
        """Execute the mission with architect-led delegation loop."""
        start_time = time.time()
        timeout = config.activity_timeout  # hard timeout for the whole mission
        turn = 0
        max_turns = min(_MAX_TURNS, self.max_depth * 4)  # bounded by config depth
        agent_results: dict[str, str] = {}  # agent_type -> result
        agents_used: set[AgentType] = set(trace.agents_used)

        try:
            architect = self.registry.get(AgentType.ARCHITECT)

            # ---- Turn loop -------------------------------------------------
            while turn < max_turns:
                turn += 1
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    logger.warning(f"Mission {trace.trace_id} timed out after {elapsed:.0f}s")
                    break

                if progress_callback:
                    try:
                        pct = min(0.9, turn / (max_turns + 1))
                        await progress_callback(pct, f"Turn {turn}/{max_turns}...")
                    except Exception:
                        logger.warning("Progress callback failed", exc_info=True)

                # Build architect prompt including delegation results
                prompt = self._build_architect_prompt(
                    trace.objective,
                    context,
                    agent_results,
                    turn,
                    max_turns,
                )

                request = GeminiRequest(
                    prompt=prompt,
                    system_instruction=architect.system_prompt,
                    model=architect.model or self.client.default_model,
                    timeout=config.activity_timeout,
                )

                response = await self.client.generate(request)
                text = response.text

                trace.messages.append(
                    SwarmMessage(
                        role="assistant",
                        content=text,
                        agent_type=AgentType.ARCHITECT,
                    )
                )

                # ---- Parse structured actions from architect output --------
                delegations = self._parse_delegations(text)
                completed = self._parse_completion(text)

                if completed is not None:
                    # Architect signalled completion.
                    trace.result = completed
                    trace.status = TaskStatus.COMPLETED
                    trace.completed_at = datetime.now()
                    trace.total_turns = turn
                    trace.agents_used = list(agents_used)
                    self.trace_store.save(trace)
                    await self.swarm_registry.unregister(trace.trace_id)

                    if progress_callback:
                        try:
                            await progress_callback(1.0, "Mission complete")
                        except Exception:
                            logger.warning("Progress callback failed", exc_info=True)

                    return SwarmResult(
                        trace_id=trace.trace_id,
                        status=TaskStatus.COMPLETED,
                        result=completed,
                        agents_used=list(agents_used),
                        tasks_completed=len(agent_results) + 1,
                        total_turns=turn,
                        elapsed_seconds=time.time() - start_time,
                    )

                if delegations:
                    # Execute delegations (up to max_depth concurrent)
                    # Time budget: remaining time from mission timeout
                    remaining_time = max(10.0, timeout - (time.time() - start_time))
                    for agent_name, task_desc in delegations[: self.max_depth]:
                        # Try built-in agent types first, then custom personas
                        agent_def = None
                        agent_type = None
                        try:
                            agent_type = AgentType(agent_name.lower())
                            agent_def = self.registry.get(agent_type)
                        except ValueError:
                            # Check custom personas
                            try:
                                if self.registry.has_custom(agent_name):
                                    agent_def = self.registry.get_by_name(agent_name)
                                    agent_type = agent_def.agent_type
                                else:
                                    logger.warning(
                                        f"Unknown agent '{agent_name}', skipping delegation"
                                    )
                                    continue
                            except (ValueError, KeyError):
                                logger.warning(
                                    f"Failed to resolve agent '{agent_name}', skipping delegation"
                                )
                                continue

                        agents_used.add(agent_type)
                        try:
                            sub_result = await asyncio.wait_for(
                                self._execute_agent(
                                    agent_def,
                                    task_desc,
                                    trace.objective,
                                    context,
                                ),
                                timeout=remaining_time,
                            )
                        except TimeoutError:
                            logger.warning(
                                f"Agent {agent_name} timed out after {remaining_time:.0f}s"
                            )
                            sub_result = f"[Agent {agent_name} timed out]"
                        agent_results[agent_type.value] = sub_result
                        trace.messages.append(
                            SwarmMessage(
                                role="assistant",
                                content=sub_result,
                                agent_type=agent_type,
                            )
                        )
                else:
                    # No delegations AND no completion — treat as final answer.
                    trace.result = text
                    trace.status = TaskStatus.COMPLETED
                    trace.completed_at = datetime.now()
                    trace.total_turns = turn
                    trace.agents_used = list(agents_used)
                    self.trace_store.save(trace)
                    await self.swarm_registry.unregister(trace.trace_id)

                    if progress_callback:
                        try:
                            await progress_callback(1.0, "Mission complete")
                        except Exception:
                            logger.warning("Progress callback failed", exc_info=True)

                    return SwarmResult(
                        trace_id=trace.trace_id,
                        status=TaskStatus.COMPLETED,
                        result=text,
                        agents_used=list(agents_used),
                        tasks_completed=len(agent_results) + 1,
                        total_turns=turn,
                        elapsed_seconds=time.time() - start_time,
                    )

            # ---- Exhausted turns / timed out ----------------------------
            final = (
                agent_results.get("architect") or trace.messages[-1].content
                if trace.messages
                else ""
            )
            trace.result = final
            trace.status = TaskStatus.COMPLETED
            trace.completed_at = datetime.now()
            trace.total_turns = turn
            trace.agents_used = list(agents_used)
            self.trace_store.save(trace)
            await self.swarm_registry.unregister(trace.trace_id)

            return SwarmResult(
                trace_id=trace.trace_id,
                status=TaskStatus.COMPLETED,
                result=final,
                agents_used=list(agents_used),
                tasks_completed=len(agent_results),
                total_turns=turn,
                elapsed_seconds=time.time() - start_time,
            )

        except Exception as e:
            logger.exception(f"Mission execution failed: {e}")
            trace.status = TaskStatus.FAILED
            trace.error = str(e)
            trace.completed_at = datetime.now()
            self.trace_store.save(trace)
            await self.swarm_registry.unregister(trace.trace_id)

            return SwarmResult(
                trace_id=trace.trace_id,
                status=TaskStatus.FAILED,
                error=str(e),
                agents_used=list(agents_used),
                elapsed_seconds=time.time() - start_time,
            )

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def _build_architect_prompt(
        self,
        objective: str,
        context: str,
        agent_results: dict[str, str],
        turn: int,
        max_turns: int,
    ) -> str:
        """Build the architect prompt including prior delegation results."""
        parts = [
            f"Mission Objective: {objective}",
        ]
        if context:
            parts.append(f"Context: {context}")

        if agent_results:
            parts.append("\n--- Results from delegated agents ---")
            for agent_name, result in agent_results.items():
                parts.append(f"\n[{agent_name}]:\n{result[:2000]}")
            parts.append("--- End of agent results ---\n")

        parts.append(f"Turn {turn}/{max_turns}.")

        # Build available agents list including custom personas
        builtin = "researcher, coder, analyst, reviewer, tester, documenter"
        custom_names = self.registry.list_custom_agents()
        if custom_names:
            custom_list = ", ".join(n.lower().replace(" ", "_") for n in custom_names)
            agents_line = f"Available agents: {builtin}, {custom_list}"
        else:
            agents_line = f"Available agents: {builtin}"

        parts.append(
            "Actions:\n"
            "  delegate(agent_name, task_description) — assign work to a specialist\n"
            "  complete(final_result) — finish the mission with your answer\n\n"
            f"{agents_line}\n\n"
            "If you can answer directly, use complete(your_answer). "
            "Otherwise delegate sub-tasks, then integrate results on the next turn."
        )
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Action parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_delegations(text: str) -> list[tuple[str, str]]:
        """Extract delegate(agent, task) calls from architect output.

        Uses ``[^)]{1,2000}`` instead of ``.*?`` with optional quotes to
        prevent catastrophic backtracking (ReDoS) on malformed input.
        """
        results: list[tuple[str, str]] = []
        for match in re.finditer(r"delegate\(([^)]{1,2000})\)", text, re.IGNORECASE):
            inner = match.group(1).strip()
            parts = inner.split(",", 1)
            if len(parts) == 2:
                agent = parts[0].strip().strip("\"'")
                task = parts[1].strip().strip("\"'")
                if re.fullmatch(r"\w+", agent):
                    results.append((agent, task))
        return results

    @staticmethod
    def _parse_completion(text: str) -> str | None:
        """Extract complete(result) from architect output."""
        match = re.search(r"complete\((.*)\)", text, re.DOTALL | re.IGNORECASE)
        if match:
            result = match.group(1).strip().strip("\"'")
            return result if result else None
        return None

    # ------------------------------------------------------------------
    # Sub-agent execution
    # ------------------------------------------------------------------

    async def _execute_agent(
        self,
        agent_def: AgentDefinition,
        task: str,
        mission_objective: str,
        context: str,
    ) -> str:
        """Execute a single specialist agent and return its response."""
        prompt = (
            f"Mission context: {mission_objective}\n\n"
            f"Your task: {task}\n\n"
            f"{f'Additional context: {context}' if context else ''}\n\n"
            f"Provide a thorough, actionable response."
        )
        request = GeminiRequest(
            prompt=prompt,
            system_instruction=agent_def.system_prompt,
            model=agent_def.model or self.client.default_model,
            timeout=config.activity_timeout,
        )
        response = await self.client.generate(request)
        return response.text

    # ------------------------------------------------------------------
    # Adjudication
    # ------------------------------------------------------------------

    async def adjudicate(
        self,
        query: str,
        panel_personas: list[str] | None = None,
        strategy: AdjudicationStrategy = AdjudicationStrategy.SUPREME_COURT,
        progress_callback: Callable[[float, str], Awaitable[None]] | None = None,
    ) -> AdjudicationResult:
        """Convene an expert panel for consensus."""
        trace_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        if not panel_personas:
            panel_personas = ["architect", "analyst", "reviewer"]

        # Cap panel size to prevent excessive API calls
        max_panel_size = 10
        if len(panel_personas) > max_panel_size:
            logger.warning(
                f"Panel size {len(panel_personas)} exceeds maximum {max_panel_size}, truncating"
            )
            panel_personas = panel_personas[:max_panel_size]

        votes: list[PanelVote] = []

        for i, persona_name in enumerate(panel_personas):
            if progress_callback:
                try:
                    progress = (i + 1) / (len(panel_personas) + 1)
                    await progress_callback(progress, f"Expert {persona_name} deliberating...")
                except Exception:
                    logger.warning("Progress callback failed", exc_info=True)

            try:
                agent_type = AgentType(persona_name.lower())
                agent = self.registry.get(agent_type)
            except (ValueError, KeyError):
                logger.warning(f"Unknown persona: {persona_name}, using analyst")
                agent_type = AgentType.ANALYST
                agent = self.registry.get(agent_type)

            prompt = f"""As a {agent.role}, provide your expert position on:

{query}

Respond in JSON with these fields:
- "position": your clear recommendation
- "reasoning": supporting arguments
- "confidence": float 0.0 to 1.0
- "concerns": list of caveats"""

            request = GeminiRequest(
                prompt=prompt,
                system_instruction=agent.system_prompt,
                model=agent.model or self.client.default_model,
            )

            response = await self.client.generate(request)

            # Parse confidence from structured output if possible
            parsed_confidence = 0.8
            try:
                json_match = re.search(r"\{[\s\S]*\}", response.text)
                if json_match:
                    parsed = json.loads(json_match.group())
                    parsed_confidence = float(parsed.get("confidence", 0.8))
                    parsed_confidence = max(0.0, min(1.0, parsed_confidence))
            except Exception:
                pass

            votes.append(
                PanelVote(
                    agent_type=agent_type,
                    position=response.text,
                    reasoning="",
                    confidence=parsed_confidence,
                )
            )

        # Synthesize verdict
        if progress_callback:
            try:
                await progress_callback(0.9, "Synthesizing verdict...")
            except Exception:
                logger.warning("Progress callback failed", exc_info=True)

        synthesis_prompt = f"""As the presiding judge, synthesize these expert opinions:

Query: {query}

Expert Opinions:
{chr(10).join([f"- {v.agent_type.value} (confidence {v.confidence:.2f}): {v.position[:500]}..." for v in votes])}

Provide in JSON:
- "verdict": final verdict
- "reasoning": synthesized reasoning
- "confidence": overall confidence (0.0-1.0)
- "dissenting_opinions": list of notable disagreements"""

        request = GeminiRequest(
            prompt=synthesis_prompt,
            system_instruction="You are a fair and balanced judge synthesizing expert opinions.",
        )

        verdict_response = await self.client.generate(request)

        # Parse synthesis for dynamic confidence + dissent
        overall_confidence = sum(v.confidence for v in votes) / max(len(votes), 1)
        dissenting: list[str] = []
        try:
            json_match = re.search(r"\{[\s\S]*\}", verdict_response.text)
            if json_match:
                parsed = json.loads(json_match.group())
                overall_confidence = float(parsed.get("confidence", overall_confidence))
                overall_confidence = max(0.0, min(1.0, overall_confidence))
                dissenting = parsed.get("dissenting_opinions", [])
                if isinstance(dissenting, str):
                    dissenting = [dissenting]
        except Exception:
            pass

        return AdjudicationResult(
            trace_id=trace_id,
            query=query,
            verdict=verdict_response.text,
            reasoning="",
            confidence=overall_confidence,
            panel_votes=votes,
            dissenting_opinions=dissenting,
            elapsed_seconds=time.time() - start_time,
        )

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    async def get_status(self, trace_id: str) -> dict | None:
        """Get status of a swarm mission."""
        if self.swarm_registry.is_running(trace_id):
            return {"trace_id": trace_id, "status": "running"}
        trace = self.trace_store.load(trace_id)
        if trace:
            return {
                "trace_id": trace_id,
                "status": trace.status.value,
                "result": trace.result,
                "error": trace.error,
            }
        return None

    async def get_trace(self, trace_id: str) -> ExecutionTrace | None:
        """Get full execution trace."""
        return self.trace_store.load(trace_id)

    async def cancel(self, trace_id: str) -> bool:
        """Cancel a running mission."""
        if self.swarm_registry.is_running(trace_id):
            await self.swarm_registry.update_status(trace_id, "cancelled")
            await self.swarm_registry.unregister(trace_id)
            return True
        return False
