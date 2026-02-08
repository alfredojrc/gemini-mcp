# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-08

### Added

- **Core tools**: `gemini`, `analyze`, `search`, `ping`
  - `gemini`: Query Gemini AI with modes — fast, reasoning, explain, summarize, models
  - `analyze`: Code/file/directory/diff analysis with focus areas (security, performance, architecture, patterns)
  - `search`: Web search with Google Search grounding (quick, deep, academic, docs)
  - `ping`: Health check returning "pong"
- **Swarm system**: Multi-agent orchestration using Supervisor Pattern
  - 7 agent types: architect, researcher, coder, analyst, reviewer, tester, documenter
  - 4 execution modes: fast, async, thorough, consensus
  - `swarm_adjudicate`: Expert panel consensus with weighted confidence scoring
  - `swarm_check`: Mission status, results, cancellation, and trace retrieval
  - TraceStore with file locking and 500-file disk quota
  - SwarmRegistry for active mission tracking
  - AsyncBlackboard for concurrent agent communication
- **Debate system**: AI-to-AI structured debates
  - 4 strategies: collaborative, adversarial, socratic, devil_advocate
  - TF-IDF cosine similarity for novelty-based convergence detection
  - Bracket-balanced JSON extraction from LLM responses
  - DebateMemory with file locking and 500-file disk quota
  - Debate search, stats, and context retrieval
- **Security**
  - Bearer token authentication for HTTP transports (`/health` exempt)
  - Path validation blocking sensitive system directories
  - Plugin allowlist with SHA-256 hash verification
  - Rate limiting via in-memory token bucket (per-IP, zero external dependencies)
  - Request size limits with 413 responses
  - Structured JSON audit logging (opt-in)
- **Configuration**: Pydantic-settings with `GEMINI_MCP_` prefix and field validators
- **Transports**: STDIO, SSE, and Streamable-HTTP support
- **Plugin system**: Auto-loading from `plugins/` with allowlist and integrity checks
- **Custom personas**: Markdown-based persona definitions in `personas/`
- **Docker deployment**: Multi-stage build, non-root container, production compose with Nginx
- **CI/CD**: GitHub Actions for testing (Python 3.11/3.12), PyPI publish, and GHCR Docker images
- **Models**: Gemini 3 preview support (gemini-3-pro-preview, gemini-3-flash-preview) with 1M token context

[1.0.0]: https://github.com/alfredojrc/gemini-mcp/releases/tag/v1.0.0
