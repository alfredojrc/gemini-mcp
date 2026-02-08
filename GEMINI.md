# Gemini MCP Server - Complete Reference

## Operational Safety Protocols

### 1. Log Inspection Protocol (CRITICAL)

When debugging or monitoring the server:

- **NEVER** dump full logs (`docker logs <container>`) - causes context overflow
- **ALWAYS** use `tail -n 20` or `grep` to filter relevant information
- **NEVER** use `-f` (follow) in synchronous commands - causes hangs

**Correct Pattern:**
```bash
docker logs gemini_mcp 2>&1 | grep -i "error" | tail -n 20
```

### 2. Command Execution Standards

- **Background Execution:** Run long commands with `&` if output not needed immediately
- **Code Quality:** Run formatters before commits:
  ```bash
  black . && ruff check .
  ```

### 3. Authentication

The server supports multiple authentication methods (priority order):

1. **API Key (Highest priority):** Set `GOOGLE_API_KEY` environment variable
2. **OAuth:** Run `gemini login` on host, mount `~/.gemini` to container
3. **Application Default Credentials (ADC):** Auto-detected from GCP environment

**HTTP Bearer Auth:** Set `GEMINI_MCP_AUTH_TOKEN` for HTTP transport authentication.
All requests (except `/health`) require `Authorization: Bearer <token>`.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              MCP CLIENT                                       │
│                    (Gemini CLI / Claude Code / Custom)                        │
└─────────────────────────────────┬────────────────────────────────────────────┘
                                  │ MCP Protocol (JSON-RPC 2.0)
                                  │
┌─────────────────────────────────▼────────────────────────────────────────────┐
│                           GEMINI MCP SERVER                                  │
│                         (FastMCP Framework)                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                     MIDDLEWARE STACK (HTTP only)                        │ │
│  │   ┌──────────────┐  ┌───────────────┐  ┌────────────────────────────┐  │ │
│  │   │ Bearer Auth  │→ │ Rate Limiting │→ │ Request Size Limit (10MB) │  │ │
│  │   │ (optional)   │  │ (token bucket)│  │ (413 on oversized)        │  │ │
│  │   └──────────────┘  └───────────────┘  └────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                  │                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                        TRANSPORT LAYER                                  │ │
│  │   ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐    │ │
│  │   │   STDIO     │    │   SSE       │    │   Streamable-HTTP       │    │ │
│  │   │ (CLI)       │    │ (HTTP)      │    │ (Stateless)             │    │ │
│  │   └─────────────┘    └─────────────┘    └─────────────────────────┘    │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                  │                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                    TOOL REGISTRY + AUDIT LOGGING                       │ │
│  │                                                                         │ │
│  │   CORE TOOLS                    OPTIONAL TOOLS                         │ │
│  │   ┌──────────┐ ┌──────────┐     ┌──────────┐ ┌──────────────────┐      │ │
│  │   │ gemini   │ │ analyze  │     │  swarm   │ │ swarm_adjudicate │      │ │
│  │   └──────────┘ └──────────┘     └──────────┘ └──────────────────┘      │ │
│  │   ┌──────────┐ ┌──────────┐     ┌──────────┐                           │ │
│  │   │  search  │ │  ping    │     │  debate  │                           │ │
│  │   └──────────┘ └──────────┘     └──────────┘                           │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                  │                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │              SUBSYSTEMS                                                 │ │
│  │  ┌────────────────┐  ┌──────────────────┐  ┌─────────────────────┐     │ │
│  │  │ SwarmOrchestrator│ │ DebateOrchestrator│ │ Plugin Loader       │     │ │
│  │  │ (Supervisor)    │ │ (TF-IDF novelty) │ │ (SHA-256 verified) │     │ │
│  │  │ TraceStore      │ │ DebateMemory     │ │ Allowlist gated    │     │ │
│  │  └────────────────┘  └──────────────────┘  └─────────────────────┘     │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                    GEMINI AI (google-genai SDK v1.62.0)                      │
│                   Gemini 3 Preview — 1M Token Context                       │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Available Tools

### Core Tools

| Tool | Description | Modes/Options |
|------|-------------|---------------|
| `gemini` | Direct AI query interface | fast, reasoning, explain, summarize, models |
| `analyze` | Code/file/directory analysis | general, security, performance, architecture, patterns |
| `search` | Web search with grounding | quick, deep, academic, docs |
| `ping` | Health check (returns "pong") | — |

### Optional Tools (Feature Flags)

| Tool | Description | Enable With |
|------|-------------|-------------|
| `swarm` | Multi-agent missions | `GEMINI_MCP_ENABLE_SWARM=true` |
| `swarm_adjudicate` | Expert panel consensus | `GEMINI_MCP_ENABLE_SWARM=true` |
| `swarm_check` | Status/manage swarm ops | `GEMINI_MCP_ENABLE_SWARM=true` |
| `debate` | AI-to-AI structured debates | `GEMINI_MCP_ENABLE_DEBATE=true` |

---

## Tool Reference

### `gemini` - AI Query Interface

```python
gemini(prompt, mode="fast", model=None, context="")
```

**Modes:**
- `fast` - Quick response using fast model (default)
- `reasoning` - Deep analysis with extended thinking
- `explain` - Detailed developer-focused explanation
- `summarize` - Bullet point summary
- `models` - List available models

**Examples:**
```python
# Quick query
gemini(prompt="What is asyncio?", mode="fast")

# Deep reasoning
gemini(prompt="Design a caching strategy for a microservices architecture", mode="reasoning")

# Get explanation
gemini(prompt="Python decorators", mode="explain")

# Summarize content
gemini(prompt="<long text>", mode="summarize")
```

### `analyze` - Code Analysis

```python
analyze(target, instruction, focus="general")
```

**Target Types:**
- File path: `/path/to/file.py`
- Directory: `/path/to/src/`
- Inline code: Multi-line code string
- Git diff: Starts with `diff --git`

**Focus Areas:**
- `general` - Overall code quality
- `security` - Vulnerability detection
- `performance` - Bottleneck identification
- `architecture` - System design review
- `patterns` - Code pattern consistency

**Validation:**
- Path validation blocks sensitive directories (`/etc`, `/proc`, `/sys`)
- Binary files detected by extension and rejected
- Prompt size validated against `max_context_tokens` (900K default)

**Examples:**
```python
# Review a file
analyze(target="/app/auth.py", instruction="Find security issues", focus="security")

# Analyze directory
analyze(target="/app/src/", instruction="Review architecture", focus="architecture")

# Review inline code
analyze(target="def login(user, pwd): ...", instruction="Security review", focus="security")

# PR diff review
analyze(target="diff --git a/file.py...", instruction="Review changes", focus="general")
```

### `search` - Web Search

```python
search(query, depth="quick", topic_context=None)
```

**Depth Levels:**
- `quick` - Single web search (default)
- `deep` - Comprehensive multi-step research
- `academic` - Scholarly sources and papers
- `docs` - Library documentation lookup

**Examples:**
```python
# Quick search
search(query="Python 3.12 new features", depth="quick")

# Deep research
search(query="microservices vs monolith", depth="deep", topic_context="startup with 5 engineers")

# Academic research
search(query="transformer attention mechanisms", depth="academic")

# Library docs
search(query="FastAPI", depth="docs", topic_context="authentication middleware")
```

---

## Swarm System

### Overview

The swarm system implements a **Supervisor Pattern**: an architect agent parses structured `delegate(agent, task)` and `complete(result)` actions, iterates with turn limits, and feeds agent results back for integration.

**Safety bounds:**
- Turn limit: `min(10, max_depth * 4)`
- Mission timeout: `config.activity_timeout` hard ceiling
- Delegation depth: `config.swarm_max_depth` (default 3)

### Agents

| Agent | Role | Best For |
|-------|------|----------|
| `architect` | System Design & Orchestration | Planning, task decomposition, decisions |
| `researcher` | Information Gathering | Web search, documentation, fact-checking |
| `coder` | Implementation | Writing code, debugging, refactoring |
| `analyst` | Data & Pattern Analysis | Root cause analysis, data patterns |
| `reviewer` | Quality Assurance | Code review, security audit |
| `tester` | Testing & Validation | Test creation, edge cases |
| `documenter` | Documentation | API docs, guides, reports |

### `swarm` - Execute Missions

```python
swarm(objective, mode="fast", agents=None, context="")
```

**Modes:**
- `fast` - Single architect agent, synchronous execution
- `thorough` - Multi-agent with decomposition, synchronous
- `consensus` - Agents debate and vote, synchronous
- `async` - Fire-and-forget, returns trace_id for later retrieval

**Examples:**
```python
# Fast mission
swarm(objective="Design a REST API for user management", mode="fast")

# Thorough mission
swarm(
    objective="Implement authentication system",
    mode="thorough",
    agents=["architect", "coder", "reviewer"]
)

# Async mission
result = swarm(objective="Comprehensive security audit", mode="async")
# Later: swarm_check(trace_id=result["trace_id"])
```

### `swarm_adjudicate` - Expert Consensus

```python
swarm_adjudicate(query, panel=None, strategy="supreme_court")
```

**Strategies:**
- `unanimous` - All panel members must agree
- `majority` - Simple majority wins
- `supreme_court` - Judge synthesizes all positions (default)

Confidence is parsed from each expert's JSON response and computed as a weighted average. Dissenting opinions are extracted from the synthesis.

### `swarm_check` - Check Progress

```python
swarm_check(trace_id=None, action="status")
```

**Actions:**
- `status` - Get current status
- `results` - Get final results
- `cancel` - Cancel running mission
- `trace` - Get full execution trace
- `list` - List recent swarms

### Data Persistence

- **TraceStore**: File-based with `filelock` `.lock` sidecars for safe concurrent access
- **Disk quota**: 500-file limit, oldest traces pruned automatically
- **SwarmRegistry**: In-memory registry of active missions
- **AsyncBlackboard**: Shared state for concurrent agent communication

---

## Debate System

### Overview

Structured AI-to-AI debates with memory persistence. Expert A uses the default model (pro, temp=0.7) and Expert B uses the fast model (flash, temp=1.0) for genuinely distinct perspectives.

**Convergence detection** uses TF-IDF cosine similarity (pure Python implementation). Novelty = 1 - similarity. Debate converges when novelty drops below `debate_novelty_threshold` (default 0.2).

**JSON extraction** from LLM responses uses a bracket-balanced parser (not greedy regex) that handles nested braces, escaped quotes, and markdown code fences.

### `debate` - AI Debates

```python
debate(topic, action="start", strategy="collaborative", context="", debate_id=None)
```

**Actions:**
- `start` - Start new debate (default)
- `list` - List past debates
- `stats` - Get debate statistics
- `search` - Search past debates
- `load` - Load specific debate (requires `debate_id`)
- `context` - Get context from related debates

**Strategies:**
- `collaborative` - Work together to find best solution
- `adversarial` - Challenge each position rigorously
- `socratic` - Question-based exploration
- `devil_advocate` - Challenge assumptions

**Examples:**
```python
# Start collaborative debate
debate(topic="Is TDD always beneficial?", strategy="collaborative")

# Adversarial debate
debate(topic="Microservices vs Monolith", strategy="adversarial")

# Search past debates
debate(topic="testing strategies", action="search")

# Get context for new debate
debate(topic="CI/CD best practices", action="context")
```

### Data Persistence

- **DebateMemory**: File-based with `filelock` for concurrent access
- **Disk quota**: 500-file limit, oldest debates pruned
- **Context truncation**: Logged with warning when debates exceed context window

---

## Security

### Bearer Token Authentication

When `GEMINI_MCP_AUTH_TOKEN` is set and transport is HTTP (SSE or streamable-http):
- All requests require `Authorization: Bearer <token>` header
- `/health` endpoint is exempt (for Docker/load-balancer probes)
- Returns 401 with `WWW-Authenticate: Bearer` on failure

### Path Validation

- File analysis validates paths against allowed roots (`GEMINI_MCP_ALLOWED_PATHS`)
- Blocks sensitive system directories: `/etc`, `/proc`, `/sys`, `/dev`, `/boot`
- Detects binary files by extension before reading
- UTF-8 strict decoding with explicit error handling

### Plugin Security

- **Allowlist**: `GEMINI_MCP_PLUGIN_ALLOWLIST` restricts loadable plugin filenames
- **SHA-256 verification**: `GEMINI_MCP_PLUGIN_REQUIRE_HASH=true` requires `.sha256` sidecar files
- **Error isolation**: Plugin load failures are caught and logged, don't crash server
- Files starting with `_` are skipped

### Rate Limiting

In-memory token bucket middleware (zero external dependencies):
- Per-client IP tracking (supports `X-Forwarded-For`)
- Configurable via `GEMINI_MCP_RATE_LIMIT` (requests/min, 0=disabled)
- Burst capacity via `GEMINI_MCP_RATE_LIMIT_BURST` (default 20)
- Returns 429 with `Retry-After` and `X-RateLimit-*` headers
- `/health` endpoint exempt

### Request Size Limits

- `GEMINI_MCP_MAX_REQUEST_SIZE` (default 10MB, 0=unlimited)
- Returns 413 on oversized request bodies

### Audit Logging

Structured JSON audit logging for all tool invocations:
- Opt-in via `GEMINI_MCP_AUDIT_LOG=true`
- Uses stdlib `logging` with custom JSON formatter
- Records tool name, parameters, and timestamp

---

## Configuration

### Environment Variables

#### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_MCP_TRANSPORT` | `stdio` | Transport: stdio, sse, streamable-http |
| `GEMINI_MCP_SERVER_PORT` | `8765` | HTTP server port (1-65535) |
| `GEMINI_MCP_SERVER_HOST` | `0.0.0.0` | Server bind address |
| `GEMINI_MCP_DEFAULT_MODEL` | `gemini-3-pro-preview` | Default model (Gemini 3) |
| `GEMINI_MCP_FAST_MODEL` | `gemini-3-flash-preview` | Fast model (Gemini 3) |
| `GEMINI_MCP_LOG_LEVEL` | `INFO` | Log level (DEBUG-CRITICAL) |
| `GEMINI_MCP_LOG_USAGE` | `true` | Enable usage logging |

#### Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | — | API key (highest priority) |
| `GEMINI_MCP_AUTH_TOKEN` | — | Bearer token for HTTP auth |
| `GEMINI_MCP_AUTO_DISCOVER_PROJECT` | `false` | Auto-discover GCP project (makes HTTP call) |

#### Timeouts

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_MCP_TIMEOUT` | `300` | Request timeout (seconds, >=1) |
| `GEMINI_MCP_ACTIVITY_TIMEOUT` | `600` | Streaming activity timeout |
| `GEMINI_MCP_REASONING_TIMEOUT` | `900` | Reasoning mode timeout |
| `GEMINI_MCP_MAX_CONTEXT_TOKENS` | `900000` | Max context tokens (>=1000) |

#### Security

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_MCP_PLUGIN_ALLOWLIST` | — | Comma-separated plugin filenames |
| `GEMINI_MCP_PLUGIN_REQUIRE_HASH` | `false` | Require SHA-256 sidecar files |
| `GEMINI_MCP_ALLOWED_PATHS` | CWD+/tmp+$HOME | Colon-separated allowed paths |
| `GEMINI_MCP_RATE_LIMIT` | `0` | Requests/min per IP (0=disabled) |
| `GEMINI_MCP_RATE_LIMIT_BURST` | `20` | Burst capacity |
| `GEMINI_MCP_MAX_REQUEST_SIZE` | `10485760` | Max request body bytes (0=unlimited) |
| `GEMINI_MCP_AUDIT_LOG` | `false` | Enable structured JSON audit logging |

#### Feature Toggles

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_MCP_ENABLE_SWARM` | `true` | Enable swarm tools |
| `GEMINI_MCP_ENABLE_DEBATE` | `true` | Enable debate tools |

#### Swarm Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_MCP_SWARM_MAX_DEPTH` | `3` | Max delegation depth (1-20) |
| `GEMINI_MCP_SWARM_MAX_AGENTS` | `10` | Max concurrent agents (1-50) |

#### Debate Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_MCP_DEBATE_MAX_ROUNDS` | `10` | Maximum debate rounds |
| `GEMINI_MCP_DEBATE_MIN_ROUNDS` | `3` | Minimum before convergence check |
| `GEMINI_MCP_DEBATE_NOVELTY_THRESHOLD` | `0.2` | Convergence threshold (0.0-1.0) |
| `GEMINI_MCP_DEBATE_TURN_TIMEOUT` | `180` | Per-turn timeout (seconds) |

#### Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_MCP_DATA_DIR` | `~/.gemini-mcp` | Base data directory |
| `GEMINI_MCP_DEBATE_STORAGE_DIR` | `~/.gemini-mcp/debates` | Debate storage |

### Transport Modes

| Mode | Port | Use Case |
|------|------|----------|
| `stdio` | N/A | CLI integration (Gemini CLI) |
| `sse` | 8765 | HTTP clients, persistent connections |
| `streamable-http` | 8765 | Stateless HTTP, load balancers |

Invalid transport values log a warning and fall back to `sse`.

---

## Custom Personas

### Creating Personas

Add Markdown files to `personas/` directory:

```markdown
# personas/my_expert.md

## Role
Description of the persona's role and expertise.

## Expertise
- Area 1
- Area 2

## Capabilities
What this persona can do.

## Tools
- analyze
- search

## Guidelines
1. Guideline one
2. Guideline two
```

### Using Custom Personas

```python
swarm(
    objective="Security audit",
    agents=["architect", "security_expert"]  # Custom persona
)
```

---

## Plugin System

### Creating Plugins

Add Python files to `plugins/` directory:

```python
# plugins/my_tool.py
from gemini_mcp.server import mcp
from gemini_mcp.core.gemini import GeminiRequest, get_client

@mcp.tool()
async def my_tool(input: str, option: int = 10) -> dict:
    """Tool description shown to MCP clients.

    Args:
        input: What to process
        option: Processing option

    Returns:
        Processing results
    """
    client = get_client()
    request = GeminiRequest(prompt=f"Process: {input}")
    response = await client.generate(request)
    return {"result": response.text}
```

Plugins are auto-loaded on server start, subject to allowlist and hash verification.

---

## Docker Deployment

### Quick Start

```bash
docker compose up -d
curl http://localhost:8765/health
# Returns: {"status": "healthy", "version": "1.0.0"}
```

### With Authentication

```bash
# Set auth token
export GEMINI_MCP_AUTH_TOKEN=your-secret-token

docker compose up -d

# Health check (no auth needed)
curl http://localhost:8765/health

# Authenticated request
curl -H "Authorization: Bearer your-secret-token" http://localhost:8765/sse
```

### With OAuth Credentials

```bash
# Mount OAuth credentials from host
GEMINI_CREDS_PATH=~/.gemini/oauth_creds.json docker compose up -d
```

### Production Setup

```bash
docker compose -f docker-compose.prod.yml up -d
```

Production includes:
- Nginx reverse proxy (connection resilience)
- Health checks
- Resource limits
- Persistent volumes

### Container Management

```bash
# View logs (filtered)
docker logs gemini_mcp 2>&1 | grep -i error | tail -20

# Restart
docker compose restart gemini-mcp

# Rebuild
docker compose build --no-cache gemini-mcp
docker compose up -d
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Auth failed | Expired credentials | Run `gemini login` or set `GOOGLE_API_KEY` |
| 401 Unauthorized | Missing/invalid bearer token | Check `Authorization: Bearer <token>` header |
| 429 Too Many Requests | Rate limit exceeded | Wait for `Retry-After` header value |
| 413 Entity Too Large | Request body too large | Reduce payload or increase `MAX_REQUEST_SIZE` |
| Timeout | Long operation | Use `mode="async"` for swarm |
| Connection reset | Server restart | Use Nginx proxy |
| No response | Model overload | Retry with backoff |
| Path blocked | Sensitive directory | Check `GEMINI_MCP_ALLOWED_PATHS` |

### Debug Mode

```bash
GEMINI_MCP_LOG_LEVEL=DEBUG gemini-mcp
```

### Health Check

```bash
curl http://localhost:8765/health
# Returns: {"status": "healthy", "version": "1.0.0"}
```

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `src/gemini_mcp/server.py` | MCP server entry point, tools, plugins, auth |
| `src/gemini_mcp/config.py` | Configuration (pydantic-settings) + validators |
| `src/gemini_mcp/middleware.py` | Rate limiting, request size limits, audit logging |
| `src/gemini_mcp/core/gemini.py` | Gemini API client (google-genai SDK) |
| `src/gemini_mcp/tools/core.py` | Core tool implementations + path validation |
| `src/gemini_mcp/swarm/core.py` | Swarm orchestrator (Supervisor Pattern) |
| `src/gemini_mcp/swarm/memory.py` | TraceStore, SwarmRegistry, Blackboard |
| `src/gemini_mcp/debate/orchestrator.py` | Debate system (TF-IDF, JSON extraction) |
| `personas/` | Custom agent personas |
| `plugins/` | Custom tool plugins |

---

## Version History

- **v1.0.0** - Initial public release
  - Core tools: gemini, analyze, search, ping
  - Swarm system: Supervisor Pattern with delegation loop, adjudication, TraceStore
  - Debate system: TF-IDF convergence, bracket-balanced JSON extraction, DebateMemory
  - Security: Bearer auth, path validation, plugin allowlist + SHA-256 verification
  - Middleware: Rate limiting (token bucket), request size limits, structured audit logging
  - Config: Pydantic-settings with field validators for all numeric/enum fields
  - Models: Gemini 3 preview (gemini-3-pro-preview, gemini-3-flash-preview)
  - Plugin architecture with error isolation
  - Docker deployment with multi-stage build
