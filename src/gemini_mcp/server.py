"""Gemini MCP Server - Main entry point.

This module defines the MCP server and registers all available tools.
"""

import hashlib
import logging
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .config import config

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional bearer-token auth via GEMINI_MCP_AUTH_TOKEN env var.
# When set, every HTTP request must include "Authorization: Bearer <token>".
# When unset (default), the server runs without auth (local-only use).
# ---------------------------------------------------------------------------
_AUTH_TOKEN: str | None = os.getenv("GEMINI_MCP_AUTH_TOKEN")

# Initialize FastMCP server
mcp = FastMCP(
    config.server_name,
    host=config.server_host,
    port=config.server_port,
)


# =============================================================================
# Health Check — HTTP endpoint for Docker/load-balancer probes + MCP tool
# =============================================================================
@mcp.custom_route(path="/health", methods=["GET"])
async def health_check(request: Request) -> Response:
    """HTTP health-check endpoint for Docker HEALTHCHECK / load balancers."""
    return JSONResponse({"status": "healthy", "version": "1.0.0"})


@mcp.tool()
def ping() -> str:
    """Health check - returns 'pong' if server is running."""
    return "pong"


# =============================================================================
# Audit Logging (opt-in via GEMINI_MCP_AUDIT_LOG=true)
# =============================================================================
from .middleware import audit_event  # noqa: E402

# =============================================================================
# Core Tools - Always Available
# =============================================================================
from .tools.core import analyze, gemini, search  # noqa: E402


@mcp.tool()
async def gemini_query(
    prompt: str,
    mode: str = "fast",
    model: str | None = None,
    context: str = "",
) -> dict | str:
    """
    Query Gemini AI with various modes.

    Args:
        prompt: Your question or request
        mode: Query mode - fast, reasoning, explain, summarize, or models
        model: Optional model override
        context: Additional context for the query

    Returns:
        AI response (text or dict with metadata)
    """
    audit_event("tool_call", tool="gemini", mode=mode, model=model or "default")
    return await gemini(prompt=prompt, mode=mode, model=model, context=context)  # type: ignore[arg-type]


@mcp.tool()
async def analyze_code(
    target: str,
    instruction: str,
    focus: str = "general",
) -> dict | str:
    """
    Analyze code, files, or directories using Gemini's 1M token context.

    Args:
        target: File path, directory path, or inline code
        instruction: What to analyze for (e.g., "Find bugs", "Review security")
        focus: Analysis focus - general, security, performance, architecture, patterns

    Returns:
        Analysis results
    """
    audit_event("tool_call", tool="analyze", focus=focus)
    return await analyze(target=target, instruction=instruction, focus=focus)  # type: ignore[arg-type]


@mcp.tool()
async def web_search(
    query: str,
    depth: str = "quick",
    topic_context: str | None = None,
) -> dict:
    """
    Search the web with Google Search integration.

    Args:
        query: What to search for
        depth: Search depth - quick, deep, academic, docs
        topic_context: Additional context for the search

    Returns:
        Search results with sources
    """
    audit_event("tool_call", tool="search", depth=depth)
    return await search(query=query, depth=depth, topic_context=topic_context)  # type: ignore[arg-type]


# =============================================================================
# Swarm Tools - Optional
# =============================================================================
if config.enable_swarm:
    from .tools.swarm_tools import swarm_adjudicate, swarm_execute, swarm_status

    @mcp.tool()
    async def swarm(
        objective: str,
        mode: str = "fast",
        agents: list[str] | None = None,
        context: str = "",
    ) -> dict:
        """
        Execute multi-agent missions with an AI team.

        Args:
            objective: What to accomplish
            mode: Execution mode - fast, thorough, consensus, async
            agents: Optional list of agent types to use
            context: Additional context

        Returns:
            Mission results with execution trace
        """
        audit_event("tool_call", tool="swarm", mode=mode)
        return await swarm_execute(objective=objective, mode=mode, agents=agents, context=context)  # type: ignore[arg-type]

    @mcp.tool()
    async def adjudicate(
        query: str,
        panel: list[str] | None = None,
        strategy: str = "supreme_court",
    ) -> dict:
        """
        Convene an expert panel to reach consensus.

        Args:
            query: The question requiring expert consensus
            panel: Optional list of expert personas
            strategy: Consensus strategy - unanimous, majority, supreme_court

        Returns:
            Panel verdict with reasoning
        """
        return await swarm_adjudicate(query=query, panel=panel, strategy=strategy)  # type: ignore[arg-type]

    @mcp.tool()
    async def swarm_check(
        trace_id: str | None = None,
        action: str = "status",
    ) -> dict:
        """
        Check status or manage swarm operations.

        Args:
            trace_id: The swarm trace ID (optional for 'list' action)
            action: What to do - status, results, cancel, trace, list

        Returns:
            Status information
        """
        return await swarm_status(trace_id=trace_id, action=action)  # type: ignore[arg-type]


# =============================================================================
# Debate Tools - Optional
# =============================================================================
if config.enable_debate:
    from .tools.debate_tools import debate

    @mcp.tool()
    async def ai_debate(
        topic: str,
        action: str = "start",
        strategy: str = "collaborative",
        context: str = "",
        debate_id: str | None = None,
    ) -> dict:
        """
        AI-to-AI debate system with memory persistence.

        Args:
            topic: Debate topic or search query
            action: What to do - start, list, stats, search, load, context
            strategy: Debate strategy for 'start' action
            context: Additional context
            debate_id: Debate ID for 'load' action

        Returns:
            Debate results or query results
        """
        audit_event("tool_call", tool="debate", action=action, strategy=strategy)
        return await debate(
            topic=topic,
            action=action,  # type: ignore[arg-type]
            strategy=strategy,
            context=context,
            debate_id=debate_id,
        )


# =============================================================================
# Plugin Loading — with allowlist, SHA-256 verification, and error isolation
# =============================================================================
# Set GEMINI_MCP_PLUGIN_ALLOWLIST to a comma-separated list of filenames
# (e.g. "my_plugin.py,tools_extra.py") to restrict which plugins can load.
# When unset, all .py files in the plugin dir are loaded (dev convenience).
#
# Set GEMINI_MCP_PLUGIN_REQUIRE_HASH=true and create a .sha256 sidecar file
# for each plugin to enable integrity verification.  The sidecar must contain
# the hex SHA-256 of the plugin file (e.g. `sha256sum my_plugin.py > my_plugin.py.sha256`).
# =============================================================================
def _verify_plugin_hash(plugin_file: Path) -> bool:
    """Return True if the plugin passes SHA-256 integrity check.

    If hash verification is not enabled (GEMINI_MCP_PLUGIN_REQUIRE_HASH != true),
    this always returns True.  When enabled, the plugin must have a matching
    .sha256 sidecar file.
    """

    if os.getenv("GEMINI_MCP_PLUGIN_REQUIRE_HASH", "").lower() != "true":
        return True

    hash_file = plugin_file.with_suffix(plugin_file.suffix + ".sha256")
    if not hash_file.exists():
        logger.warning(f"Plugin hash file missing: {hash_file}")
        return False

    expected = hash_file.read_text().strip().split()[0].lower()
    actual = hashlib.sha256(plugin_file.read_bytes()).hexdigest()
    if actual != expected:
        logger.error(
            f"Plugin hash mismatch for {plugin_file.name}: "
            f"expected {expected[:16]}… got {actual[:16]}…"
        )
        return False
    return True


def load_plugins() -> None:
    """Load plugins from the plugin directory with safety checks."""
    import importlib.util

    plugin_dir = os.getenv("PLUGIN_DIR", str(config.data_dir / "plugins"))
    plugin_path = Path(plugin_dir)

    if not plugin_path.exists():
        logger.debug(f"Plugin directory not found: {plugin_path}")
        return

    # Optional allowlist — when set, only listed filenames are loaded.
    raw_allowlist = os.getenv("GEMINI_MCP_PLUGIN_ALLOWLIST", "").strip()
    allowlist: set[str] | None = (
        {n.strip() for n in raw_allowlist.split(",") if n.strip()} if raw_allowlist else None
    )

    for plugin_file in sorted(plugin_path.glob("*.py")):
        if plugin_file.name.startswith("_"):
            continue

        # --- Allowlist gate (check relative path, not just filename) ---
        try:
            check_name = str(plugin_file.relative_to(plugin_path))
        except ValueError:
            check_name = plugin_file.name
        if allowlist is not None and check_name not in allowlist:
            logger.debug(f"Plugin not in allowlist, skipping: {check_name}")
            continue

        # --- Integrity gate ---
        if not _verify_plugin_hash(plugin_file):
            logger.warning(f"Plugin failed integrity check, skipping: {plugin_file.name}")
            continue

        try:
            spec = importlib.util.spec_from_file_location(plugin_file.stem, plugin_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                logger.info(f"Loaded plugin: {plugin_file.name}")
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_file.name}: {e}")


# =============================================================================
# Entry Point
# =============================================================================
def _run_with_auth() -> None:
    """Start the server with auth + optional rate limiting + size limits.

    Uses Starlette mounting pattern from MCP SDK docs: get the inner app
    via mcp.sse_app(), wrap it in a Starlette app with middleware stack,
    then run via uvicorn directly.

    All middleware use pure ASGI protocol (not BaseHTTPMiddleware) to avoid
    SSE streaming buffer issues. See middleware.py docstring for details.
    """
    import uvicorn
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.routing import Mount

    from .middleware import BearerAuthMiddleware, RateLimitMiddleware, RequestSizeLimitMiddleware

    token = _AUTH_TOKEN or config.auth_token

    # Build middleware stack: auth first, then rate limit, then size limit
    middleware = [Middleware(BearerAuthMiddleware, token=token)]

    if config.rate_limit > 0:
        middleware.append(
            Middleware(
                RateLimitMiddleware,
                rate=config.rate_limit,
                burst=config.rate_limit_burst,
            )
        )
        logger.info(
            f"Rate limiting enabled: {config.rate_limit}/min (burst: {config.rate_limit_burst})"
        )

    if config.max_request_size > 0:
        middleware.append(Middleware(RequestSizeLimitMiddleware, max_size=config.max_request_size))

    # The SSE app manages its own lifecycle — no external lifespan needed.
    app = Starlette(
        routes=[Mount("/", app=mcp.sse_app())],
        middleware=middleware,
    )

    logger.info("Bearer-token authentication enabled")
    uvicorn.run(app, host=config.server_host, port=config.server_port)


def _load_personas() -> None:
    """Load custom persona definitions from the personas directory."""
    from .swarm.agents import get_agent_registry

    personas_dir = Path(__file__).resolve().parent.parent.parent / "personas"
    env_dir = os.getenv("GEMINI_MCP_PERSONAS_DIR")
    if env_dir:
        personas_dir = Path(env_dir)

    registry = get_agent_registry()
    count = registry.load_personas_from_dir(personas_dir)
    if count:
        logger.info(f"Loaded {count} custom persona(s): {', '.join(registry.list_custom_agents())}")


def main() -> None:
    """Run the Gemini MCP server."""
    # Load plugins and personas
    load_plugins()
    _load_personas()

    # Log startup info
    logger.info(f"Starting {config.server_name} v1.1.0")
    logger.info(f"Transport: {config.transport}")
    logger.info(f"Swarm enabled: {config.enable_swarm}")
    logger.info(f"Debate enabled: {config.enable_debate}")

    valid_transports = {"stdio", "sse", "streamable-http"}
    transport = config.transport
    if transport not in valid_transports:
        logger.warning(
            f"Unknown transport '{transport}', falling back to 'sse'. "
            f"Valid options: {', '.join(sorted(valid_transports))}"
        )
        transport = "sse"

    # If auth token is set and using HTTP transport, run with auth middleware
    if (_AUTH_TOKEN or config.auth_token) and transport != "stdio":
        _run_with_auth()
    else:
        mcp.run(transport=transport)


if __name__ == "__main__":
    main()
