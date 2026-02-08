# gemini-mcp

[![CI](https://github.com/alfredojrc/gemini-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/alfredojrc/gemini-mcp/actions/workflows/ci.yml)
[![Security](https://github.com/alfredojrc/gemini-mcp/actions/workflows/security.yml/badge.svg)](https://github.com/alfredojrc/gemini-mcp/actions/workflows/security.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)

A Model Context Protocol (MCP) server wrapping Google's Gemini AI, enabling AI assistants to leverage Gemini 3's 1M token context window for complex tasks including multi-agent orchestration and AI-to-AI debates.

## Features

- **Unified AI Interface**: Query Gemini 3 with multiple modes (fast, reasoning, explain, summarize)
- **Code Analysis**: Analyze files, directories, and diffs with automatic binary file detection
- **Web Search**: Integrated Google Search grounding (quick, deep, academic, docs)
- **Multi-Agent Swarm**: Supervisor-pattern delegation with 7 specialized agent types
- **AI Debates**: Structured AI-to-AI debates with TF-IDF novelty detection and persistence
- **Security**: Bearer token auth (constant-time, RFC 7235), pure ASGI middleware, path validation, rate limiting with LRU eviction, CI vulnerability scanning
- **Plugin System**: Extend functionality with custom tools (allowlist + hash verification)
- **Multiple Transports**: STDIO, SSE, and Streamable-HTTP support

## Quick Start

### Prerequisites

- Python 3.11+
- Google Gemini API key or Gemini CLI authenticated (`gemini login`)
- Docker (recommended) or local Python environment

### Installation

#### Option 1: Docker (Recommended)

```bash
git clone https://github.com/alfredojrc/gemini-mcp.git
cd gemini-mcp

# Copy and configure environment
cp .env.example .env
# Edit .env with your API key or OAuth credentials

# Start the server
docker compose up -d

# Verify it's running
curl http://localhost:8765/health
```

#### Option 2: Local Installation

```bash
pip install -e .
gemini-mcp
```

### Connect Your MCP Client

**Claude Code:**
```bash
claude mcp add gemini-mcp http://localhost:8765/sse --transport sse
```

**Gemini CLI** (`~/.gemini/settings.json`):
```json
{
  "mcpServers": {
    "gemini-mcp": {
      "url": "http://localhost:8765/sse"
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `gemini` | Query Gemini AI — modes: `fast`, `reasoning`, `explain`, `summarize`, `models` |
| `analyze` | Analyze code files, directories, diffs, or inline snippets |
| `search` | Web search — depth: `quick`, `deep`, `academic`, `docs` |
| `swarm` | Execute multi-agent missions — modes: `fast`, `async`, `thorough`, `consensus` |
| `swarm_adjudicate` | Expert panel consensus with weighted confidence scoring |
| `debate` | AI-to-AI structured debates with 4 strategies |

### Examples

```python
# Quick AI query (uses gemini-3-flash-preview)
gemini(prompt="Explain async/await in Python", mode="fast")

# Deep reasoning (uses gemini-3-pro-preview with thinking config)
gemini(prompt="Design a distributed cache", mode="reasoning")

# Analyze a codebase for security issues
analyze(target="/path/to/project", instruction="Find security issues", focus="security")

# Review a PR diff
analyze(target="diff --git a/file.py ...", instruction="Review this PR", focus="general")

# Deep research with Google Search grounding
search(query="React Server Components best practices 2026", depth="deep")

# Multi-agent mission (architect delegates to specialist agents)
swarm(objective="Design a REST API for a todo app", mode="thorough")

# AI debate with novelty-based convergence
debate(topic="Microservices vs monolith for a startup?", strategy="adversarial", rounds=5)
```

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      MCP CLIENT                               │
│               (Gemini CLI / Claude / Custom)                  │
└──────────────────────────┬───────────────────────────────────┘
                           │ MCP Protocol (JSON-RPC 2.0)
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                  PURE ASGI MIDDLEWARE STACK                    │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ BearerAuth → RateLimit → SizeLimit → MCP Server      │    │
│  │ (hmac)       (LRU)       (chunked)                    │    │
│  └──────────────────────────────────────────────────────┘    │
├──────────────────────────────────────────────────────────────┤
│                     GEMINI-MCP SERVER                         │
│                                                               │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌────────────┐  │
│  │  gemini  │  │ analyze  │  │  search   │  │  plugins   │  │
│  └──────────┘  └──────────┘  └───────────┘  └────────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────────────┐  │
│  │  swarm   │  │  debate  │  │  /health (no auth)        │  │
│  └────┬─────┘  └────┬─────┘  └───────────────────────────┘  │
│       │              │                                        │
│  ┌────▼─────┐  ┌────▼─────────────────┐                     │
│  │TraceStore│  │DebateMemory (TF-IDF) │                     │
│  │(filelock)│  │(filelock + quotas)    │                     │
│  └──────────┘  └──────────────────────┘                     │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│              GEMINI AI (google-genai SDK)                     │
│   gemini-3-pro-preview  |  gemini-3-flash-preview            │
│                  1M Token Context                             │
└──────────────────────────────────────────────────────────────┘
```

## Configuration

All settings use the `GEMINI_MCP_` prefix. See `.env.example` for the complete reference.

### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_MCP_TRANSPORT` | `sse` | Transport: `stdio`, `sse`, `streamable-http` |
| `GEMINI_MCP_SERVER_PORT` | `8765` | Server port (1-65535) |
| `GEMINI_MCP_SERVER_HOST` | `0.0.0.0` | Server bind address |
| `GEMINI_MCP_DEFAULT_MODEL` | `gemini-3-pro-preview` | Default model for reasoning |
| `GEMINI_MCP_FAST_MODEL` | `gemini-3-flash-preview` | Fast model for quick queries |
| `GOOGLE_API_KEY` | — | API key (alternative to OAuth) |

### Security

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_MCP_AUTH_TOKEN` | — | Bearer token for HTTP auth (leave empty for local use) |
| `GEMINI_MCP_PLUGIN_ALLOWLIST` | — | Comma-separated plugin file allowlist |
| `GEMINI_MCP_PLUGIN_REQUIRE_HASH` | `false` | Require `.sha256` sidecar for plugins |
| `GEMINI_MCP_ALLOWED_PATHS` | CWD+/tmp+$HOME | Colon-separated allowed base directories |

### Timeouts

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_MCP_TIMEOUT` | `300` | Request timeout (seconds) |
| `GEMINI_MCP_ACTIVITY_TIMEOUT` | `600` | Streaming activity timeout |
| `GEMINI_MCP_REASONING_TIMEOUT` | `900` | Deep analysis timeout |
| `GEMINI_MCP_MAX_CONTEXT_TOKENS` | `900000` | Max prompt tokens (Gemini 3 supports 1M) |

### Rate Limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_MCP_RATE_LIMIT` | `0` | Requests per minute per IP (0 = disabled) |
| `GEMINI_MCP_RATE_LIMIT_BURST` | `20` | Burst capacity before throttling |
| `GEMINI_MCP_MAX_REQUEST_SIZE` | `10485760` | Max request body in bytes (0 = unlimited) |

### Swarm

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_MCP_ENABLE_SWARM` | `true` | Enable swarm tools |
| `GEMINI_MCP_SWARM_MAX_DEPTH` | `3` | Max delegation depth (1-20) |
| `GEMINI_MCP_SWARM_MAX_AGENTS` | `10` | Max concurrent agents (1-50) |
| `GEMINI_MCP_SWARM_MAX_TURNS` | `10` | Max delegation turns per mission |

### Debate

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_MCP_ENABLE_DEBATE` | `true` | Enable debate tools |
| `GEMINI_MCP_DEBATE_MAX_ROUNDS` | `10` | Max debate rounds |
| `GEMINI_MCP_DEBATE_MIN_ROUNDS` | `3` | Min rounds before convergence check |
| `GEMINI_MCP_DEBATE_NOVELTY_THRESHOLD` | `0.2` | Convergence threshold (0.0-1.0) |
| `GEMINI_MCP_DEBATE_TURN_TIMEOUT` | `180` | Per-turn timeout (seconds) |

## Swarm System

The swarm uses a **Supervisor Pattern** where an architect agent delegates tasks to specialists:

```
Architect (gemini-3-pro-preview)
  ├── delegate("researcher", "gather information about...")
  ├── delegate("coder", "implement the solution...")
  ├── delegate("reviewer", "review the code for...")
  └── complete("Final synthesized result...")
```

### Agent Types

| Agent | Role | Specialization |
|-------|------|----------------|
| `architect` | System design, task decomposition | Delegation, synthesis |
| `researcher` | Information gathering | Analysis, search |
| `coder` | Implementation | Code generation, debugging |
| `analyst` | Data patterns | Root cause, metrics |
| `reviewer` | Quality assurance | Code review, testing |
| `tester` | Validation | Test creation, edge cases |
| `documenter` | Documentation | Guides, API docs |

### Execution Modes

| Mode | Behavior |
|------|----------|
| `fast` | Single architect pass (synchronous) |
| `async` | Background execution, poll with `swarm_status` |
| `thorough` | Architect + coder + reviewer pipeline |
| `consensus` | Architect + analyst + reviewer pipeline |

## Debate System

AI-to-AI debates using distinct models for genuine diversity of perspective:

- **Expert A**: `gemini-3-pro-preview` (temperature 0.7) — measured, analytical
- **Expert B**: `gemini-3-flash-preview` (temperature 1.0) — creative, exploratory

### Strategies

| Strategy | Behavior |
|----------|----------|
| `collaborative` | Experts build on each other's ideas |
| `adversarial` | Experts challenge opposing views |
| `socratic` | Question-based exploration |
| `devil_advocate` | One expert systematically challenges |

### Convergence Detection

Uses TF-IDF cosine similarity to detect when arguments stop introducing new ideas. When novelty drops below the threshold (default 0.2), the debate concludes with a synthesis.

## Plugin System

Extend gemini-mcp with custom tools in the `plugins/` directory:

```python
# plugins/my_tool.py
from gemini_mcp.server import mcp

@mcp.tool()
async def my_custom_tool(arg1: str, arg2: int = 10) -> dict:
    """My custom tool description."""
    return {"result": f"Processed {arg1} with {arg2}"}
```

### Plugin Security

- **Allowlist**: Set `GEMINI_MCP_PLUGIN_ALLOWLIST=my_tool.py,other.py` to restrict which plugins load
- **Hash Verification**: Set `GEMINI_MCP_PLUGIN_REQUIRE_HASH=true` and create `.sha256` sidecar files:
  ```bash
  sha256sum plugins/my_tool.py | cut -d' ' -f1 > plugins/my_tool.py.sha256
  ```

## Docker Deployment

### Basic

```bash
docker compose up -d
```

### With Authentication

```bash
# Set auth token in .env
echo "GEMINI_MCP_AUTH_TOKEN=$(openssl rand -hex 32)" >> .env
docker compose up -d

# All requests now require the token
curl -H "Authorization: Bearer $GEMINI_MCP_AUTH_TOKEN" http://localhost:8765/sse
```

### Credential Mounting

The Docker container supports two authentication methods:

1. **API Key** (simplest): Set `GOOGLE_API_KEY` in `.env`
2. **OAuth**: Set `GEMINI_CREDS_PATH` to your local credentials file path

```yaml
# docker-compose.yml mounts credentials automatically:
# ${GEMINI_CREDS_PATH:-/dev/null}:/home/app/.gemini/oauth_creds.json:ro
```

### Internal Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_MCP_MAX_TRACE_FILES` | `500` | Max trace files before oldest pruned |
| `GEMINI_MCP_MAX_DEBATE_FILES` | `500` | Max debate files before oldest pruned |
| `GEMINI_MCP_RESULT_TRUNCATION_CHARS` | `2000` | Agent result truncation length |

### Production Stack

See `docker-compose.prod.yml` for a production setup with:
- Nginx reverse proxy for connection resilience
- Qdrant vector database for knowledge storage (opt-in via `--profile qdrant`)
- Persistent volumes for data

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests (in Docker — recommended)
docker build -f docker/Dockerfile -t gemini-mcp:test .
docker run --rm gemini-mcp:test pytest tests/ -v

# Run tests (local)
pytest tests/ -v

# Format and lint
black src/ tests/
ruff check src/ tests/

# Type check
mypy src/
```

## Troubleshooting

### Authentication Issues

1. Ensure Gemini CLI is authenticated:
   ```bash
   gemini login
   ```
2. Or set `GOOGLE_API_KEY` environment variable

### Connection Timeouts

For long-running operations, the server uses streaming with heartbeats. If you experience timeouts:

1. Increase client timeout settings
2. Use `mode="async"` for swarm operations
3. Check `swarm_status(trace_id="...")` for results

### Debug Mode

```bash
GEMINI_MCP_LOG_LEVEL=DEBUG gemini-mcp
```

## License

MIT License — see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Google Gemini](https://deepmind.google/technologies/gemini/) for the AI backbone
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) for the protocol implementation
- [FastMCP](https://github.com/jlowin/fastmcp) for the server framework
- [Trivy](https://trivy.dev/) for container and dependency vulnerability scanning
