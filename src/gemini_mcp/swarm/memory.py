"""Memory and persistence for the Swarm system."""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from filelock import FileLock, Timeout

from ..config import config
from .types import ExecutionTrace, TaskStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Disk-quota constants
# ---------------------------------------------------------------------------
_MAX_TRACE_FILES = 500  # prune oldest when exceeded


class TraceStore:
    """Persistent storage for execution traces with file locking and disk quotas.

    Uses ``filelock`` for safe concurrent access — each trace file gets a
    ``.lock`` sidecar so multiple async tasks can write simultaneously without
    corrupting individual files.
    """

    def __init__(self) -> None:
        self.storage_dir = config.data_dir / "swarm" / "traces"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _lock_for(self, trace_file: Path) -> FileLock:
        """Return a FileLock sidecar for *trace_file*."""
        return FileLock(str(trace_file) + ".lock", timeout=5)

    def save(self, trace: ExecutionTrace) -> None:
        """Save trace to disk with file locking and quota enforcement."""
        trace_file = self.storage_dir / f"{trace.trace_id}.json"
        data = {
            "trace_id": trace.trace_id,
            "objective": trace.objective,
            "status": trace.status.value,
            "agents_used": [a.value for a in trace.agents_used],
            "result": trace.result,
            "error": trace.error,
            "total_turns": trace.total_turns,
            "created_at": trace.created_at.isoformat(),
            "completed_at": (
                trace.completed_at.isoformat() if trace.completed_at else None
            ),
        }
        try:
            with self._lock_for(trace_file):
                trace_file.write_text(json.dumps(data, indent=2))
        except Timeout:
            logger.warning(
                f"Lock timeout writing trace {trace.trace_id}, writing without lock"
            )
            trace_file.write_text(json.dumps(data, indent=2))

        self._enforce_quota()

    def _enforce_quota(self) -> None:
        """Remove oldest trace files when over quota."""
        files = sorted(self.storage_dir.glob("*.json"), key=lambda f: f.stat().st_mtime)
        while len(files) > _MAX_TRACE_FILES:
            oldest = files.pop(0)
            oldest.unlink(missing_ok=True)
            # Clean up sidecar lock file
            lock_file = Path(str(oldest) + ".lock")
            lock_file.unlink(missing_ok=True)
            logger.debug(f"Pruned old trace: {oldest.name}")

    def load(self, trace_id: str) -> ExecutionTrace | None:
        """Load trace from disk with file locking."""
        trace_file = self.storage_dir / f"{trace_id}.json"
        if not trace_file.exists():
            return None

        try:
            with self._lock_for(trace_file):
                data = json.loads(trace_file.read_text())
            from .types import AgentType

            return ExecutionTrace(
                trace_id=data["trace_id"],
                objective=data["objective"],
                status=TaskStatus(data["status"]),
                agents_used=[AgentType(a) for a in data.get("agents_used", [])],
                result=data.get("result"),
                error=data.get("error"),
                total_turns=data.get("total_turns", 0),
                created_at=datetime.fromisoformat(data["created_at"]),
                completed_at=(
                    datetime.fromisoformat(data["completed_at"])
                    if data.get("completed_at")
                    else None
                ),
            )
        except Timeout:
            logger.warning(f"Lock timeout reading trace {trace_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to load trace {trace_id}: {e}")
            return None

    def list_recent(self, limit: int = 10) -> list[dict]:
        """List recent traces."""
        traces = []
        for trace_file in sorted(
            self.storage_dir.glob("*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )[:limit]:
            try:
                data = json.loads(trace_file.read_text())
                traces.append(
                    {
                        "trace_id": data["trace_id"],
                        "objective": data["objective"][:100],
                        "status": data["status"],
                        "created_at": data["created_at"],
                    }
                )
            except Exception:
                pass
        return traces


class SwarmRegistry:
    """In-memory registry for running swarms."""

    def __init__(self) -> None:
        self._running: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    async def register(self, trace_id: str, objective: str) -> None:
        """Register a running swarm."""
        async with self._lock:
            self._running[trace_id] = {
                "objective": objective,
                "started_at": datetime.now().isoformat(),
                "status": "running",
            }

    async def update_status(self, trace_id: str, status: str) -> None:
        """Update swarm status."""
        async with self._lock:
            if trace_id in self._running:
                self._running[trace_id]["status"] = status

    async def unregister(self, trace_id: str) -> None:
        """Unregister a completed swarm."""
        async with self._lock:
            self._running.pop(trace_id, None)

    def list_running(self) -> list[dict]:
        """List currently running swarms."""
        return [{"trace_id": tid, **info} for tid, info in self._running.items()]

    def is_running(self, trace_id: str) -> bool:
        """Check if a swarm is running."""
        return trace_id in self._running


class AsyncBlackboard:
    """Shared memory for agent communication."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def write(self, key: str, value: Any) -> None:
        """Write a value to the blackboard."""
        async with self._lock:
            self._data[key] = {
                "value": value,
                "timestamp": datetime.now().isoformat(),
            }

    async def read(self, key: str) -> Any:
        """Read a value from the blackboard."""
        async with self._lock:
            entry = self._data.get(key)
            return entry["value"] if entry else None

    async def list_keys(self) -> list[str]:
        """List all keys in the blackboard."""
        async with self._lock:
            return list(self._data.keys())

    async def clear(self) -> None:
        """Clear the blackboard."""
        async with self._lock:
            self._data.clear()


# Global instances
_trace_store: TraceStore | None = None
_swarm_registry: SwarmRegistry | None = None


def get_trace_store() -> TraceStore:
    """Get the global trace store."""
    global _trace_store
    if _trace_store is None:
        _trace_store = TraceStore()
    return _trace_store


def get_swarm_registry() -> SwarmRegistry:
    """Get the global swarm registry."""
    global _swarm_registry
    if _swarm_registry is None:
        _swarm_registry = SwarmRegistry()
    return _swarm_registry
