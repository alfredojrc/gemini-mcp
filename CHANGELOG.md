# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-02-08

### Security

- **Pure ASGI middleware**: Rewrote all middleware (auth, rate limit, size limit) from Starlette `BaseHTTPMiddleware` to pure ASGI `__call__(scope, receive, send)` protocol — eliminates SSE streaming buffer, background task blocking, and ContextVar propagation issues
- **Timing attack fix**: Bearer token comparison now uses `hmac.compare_digest()` for constant-time comparison
- **CVE-2026-22701**: Bumped `filelock` to `>=3.20.3` (TOCTOU symlink race fix)
- **ReDoS prevention**: Delegation parsing uses `[^)]{1,2000}` character class instead of vulnerable `(.*?)` regex
- **Path traversal fix**: Plugin allowlist now validates relative paths via `relative_to()`, not just filename
- **Thread-safe client**: Gemini client singleton uses double-checked locking with `threading.Lock`
- **CI vulnerability scanning**: Added GitHub Actions workflow with Trivy (Docker image + filesystem) and pip-audit

### Fixed

- **Client None guard**: `generate()` and `stream()` raise `GeminiAPIError` if client is uninitialized
- **Rate limiter memory**: LRU eviction at 10,000 buckets prevents unbounded growth from rotating-IP attacks
- **Delegation timeout**: Each sub-agent now uses `asyncio.wait_for()` with remaining mission time budget
- **Chunked encoding bypass**: Request size limit middleware now wraps `receive()` to count streamed body bytes
- **TraceStore quota race**: `_enforce_quota()` protected by `threading.Lock` for thread-safe pruning
- **Lock timeout**: On lock timeout, `save()` skips write (instead of writing without lock)
- **Path validation order**: `analyze()` checks paths before inline code detection
- **File size check**: Directory analysis checks `stat().st_size` before reading files
- **Registry leak**: `_run_and_persist()` uses `finally` to ensure `unregister()` runs on cancellation
- **Callback safety**: All progress callbacks wrapped in `try/except` to prevent mission crashes
- **Panel cap**: Adjudication panel capped at 10 personas
- **Empty completion**: `_parse_completion()` returns `None` for empty strings
- **Bare except**: Directory analysis logs debug message instead of silent `except: pass`
- **Token validation**: Added to all 7 API code paths (`_review_code`, `_review_diff`, `_search_*`, `_explain_architecture`)
- **Bearer case**: Case-insensitive "Bearer" prefix per RFC 7235
- **Debate strategy validation**: Unknown strategies return error with valid options list
- **Docker HEALTHCHECK**: Fixed build-time `${GEMINI_MCP_SERVER_PORT}` variable substitution (now hardcoded to match EXPOSE)

### Changed

- **MCP SDK**: Bumped from `mcp==1.23.0` to `mcp>=1.25.0,<2.0` (prepares for MCP SDK v2 Q1 2026)
- **google-genai**: Pinned `>=1.50.0,<2.0` (ensures Gemini 3 support)
- **httpx**: Bumped minimum to `>=0.27.0`
- **Magic numbers to config**: `swarm_max_turns`, `max_trace_files`, `max_debate_files`, `result_truncation_chars` are now configurable via `GEMINI_MCP_` environment variables

### Added

- **Input length validation**: `objective`, `topic`, `context` parameters validated against `max_context_tokens * 4` to prevent memory exhaustion
- **Security scanning CI**: `security.yml` workflow with Trivy image/filesystem scanning and pip-audit

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

[1.1.0]: https://github.com/alfredojrc/gemini-mcp/releases/tag/v1.1.0
[1.0.0]: https://github.com/alfredojrc/gemini-mcp/releases/tag/v1.0.0
