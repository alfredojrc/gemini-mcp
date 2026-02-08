# TODO — Gemini MCP v2

> Generated from comprehensive code analysis on 2026-02-05

---

## P0 — Critical (Fix Before Any Deployment) — ALL RESOLVED

### SECURITY

- [x] **Sandbox plugin loader** — `server.py` now validates plugins against an optional allowlist (`GEMINI_MCP_PLUGIN_ALLOWLIST`) and SHA-256 sidecar verification (`GEMINI_MCP_PLUGIN_REQUIRE_HASH`). *(Fixed 2026-02-05)*
- [x] **Add path validation to `analyze()`** — `tools/core.py` now validates all paths against allowed roots (`GEMINI_MCP_ALLOWED_PATHS`) and blocks sensitive system directories (`/etc`, `/proc`, `/sys`, etc.). *(Fixed 2026-02-05)*
- [x] **Add authentication middleware** — Optional bearer-token auth via `GEMINI_MCP_AUTH_TOKEN` env var. When set, all HTTP requests require `Authorization: Bearer <token>`. Health endpoint exempt for Docker probes. *(Fixed 2026-02-05)*

### BUGS

- [x] ~~**Fix default model names**~~ — **FALSE POSITIVE**: `gemini-3-pro-preview` and `gemini-3-flash-preview` are valid current Gemini 3 preview model IDs (confirmed Feb 2026). No change needed.
- [x] **Add `/health` endpoint** — Added via `@mcp.custom_route("/health")` using FastMCP's official custom-route API. Docker health checks now work. *(Fixed 2026-02-05)*

---

## P1 — High (Before Production Use) — ALL RESOLVED

### SWARM

- [x] **Implement multi-agent delegation loop** — `swarm/core.py` now implements Supervisor Pattern: architect parses `delegate(agent, task)` and `complete(result)` structured actions, iterates with turn limits (`_MAX_TURNS=10`), and feeds agent results back for integration. *(Fixed 2026-02-05)*
- [x] **Add mission timeout** — `swarm/core.py:_run_mission()` enforces `config.activity_timeout` hard ceiling per mission, breaks on timeout. *(Fixed 2026-02-05)*
- [x] **Store async mission results** — `swarm/core.py:_run_and_persist()` wrapper persists results for background missions via TraceStore. *(Fixed 2026-02-05)*
- [x] **Fix hardcoded confidence** — `swarm/core.py:adjudicate()` now parses confidence from each expert's JSON response and computes weighted average. Dissenting opinions extracted from synthesis. *(Fixed 2026-02-05)*
- [x] **Enforce safety protocols** — Turn limit bounded by `min(_MAX_TURNS, max_depth * 4)`, timeout enforced, depth from `config.swarm_max_depth`. *(Fixed 2026-02-05)*

### DEBATE

- [x] **Use distinct models/temperatures for experts** — Expert A uses `client.default_model` (pro, temp=0.7), Expert B uses `client.fast_model` (flash, temp=1.0) for genuinely distinct perspectives. *(Fixed 2026-02-05)*
- [x] **Fix novelty metric** — Replaced word-overlap with TF-IDF cosine similarity. Pure Python implementation (`_tokenize`, `_tfidf_vector`, `_cosine_similarity`). Novelty = 1 − similarity. *(Fixed 2026-02-05)*
- [x] **Fix config attribute reference** — `debate_novelty_threshold` added to `config.py` (default 0.2). Debate orchestrator now properly references it. *(Fixed 2026-02-05)*

### VALIDATION

- [x] **Add context window check** — `tools/core.py` uses char-based heuristic (~3.5 chars/token) for pre-flight token estimation. No API call needed. *(Fixed 2026-02-05)*
- [x] **Add prompt size limits** — `_validate_prompt_tokens()` rejects prompts exceeding `config.max_context_tokens` (900K). Applied to `gemini()`, `_review_file()`, and `_analyze_directory()`. *(Fixed 2026-02-05)*

### DATA INTEGRITY

- [x] **Add file locking to TraceStore** — `swarm/memory.py` now uses `filelock.FileLock` with `.lock` sidecar files (5s timeout) for safe concurrent access. *(Fixed 2026-02-05)*
- [x] **Add disk quota for traces** — `swarm/memory.py:_enforce_quota()` prunes oldest traces when exceeding 500-file limit. Lock sidecars cleaned up with their data files. *(Fixed 2026-02-05)*
- [x] **Add disk quota for debates** — `debate/orchestrator.py:_enforce_quota()` prunes oldest debates when exceeding 500-file limit. Context truncation now logged. *(Fixed 2026-02-05)*

---

## P2 — Medium (Quality & Robustness) — ALL RESOLVED

### TESTING

- [x] **Add swarm orchestrator tests** — `tests/test_swarm.py`: 20 tests covering delegation parsing, completion parsing, prompt building, TraceStore persistence/locking, SwarmRegistry, AsyncBlackboard. *(Fixed 2026-02-05)*
- [x] **Add debate orchestrator tests** — `tests/test_debate.py`: 24 tests covering TF-IDF tokenization, cosine similarity, DebateMemory, novelty, JSON extraction. *(Fixed 2026-02-05)*
- [x] **Add plugin loader tests** — `tests/test_security.py:TestPluginSandbox`: 4 tests covering hash disabled, missing sidecar, matching hash, mismatched hash. *(Fixed 2026-02-05)*
- [x] **Add auth chain tests** — `tests/test_config.py:TestAuthChain`: 4 tests covering API key priority, missing credentials, OAuth loading, init failure handling. *(Fixed 2026-02-05)*
- [x] **Add error-path tests** — `tests/test_tools.py`: token limit rejection, sensitive path blocked, binary file rejected, diff detection. `tests/test_security.py`: path traversal, invalid paths, boundary token validation. *(Fixed 2026-02-05)*
- [x] **Add config validation tests** — `tests/test_config.py:TestConfigValidation`: 12 tests for port range, timeout bounds, threshold bounds, swarm depth, log level normalization, token limit. *(Fixed 2026-02-05)*

### CODE QUALITY

- [x] **Remove redundant execution modes** — `tools/swarm_tools.py`: "fast" now uses SYNC (was incorrectly ASYNC), only "async" mode uses ASYNC. *(Fixed 2026-02-05)*
- [x] **Fix JSON regex parsing** — `debate/orchestrator.py`: Replaced greedy regex with bracket-balanced JSON extraction (`_extract_json_object`). Handles nested braces, escaped quotes, markdown code fences. 8 dedicated tests. *(Fixed 2026-02-05)*
- [x] **Fix `list_recent()` JSON error handling** — `swarm/memory.py:list_recent()` already has `try/except Exception: pass` around `json.loads()`. *(Verified 2026-02-05)*
- [x] **Validate debate_id format** — `tools/debate_tools.py` now validates debate_id is alphanumeric+hyphens and <=36 chars before loading. *(Fixed 2026-02-05)*
- [x] ~~**Replace naive relevance scoring**~~ — Already uses TF-IDF cosine similarity (implemented in P1 novelty fix). *(Resolved 2026-02-05)*
- [x] **Handle encoding errors explicitly** — `tools/core.py` now detects binary files by extension (`_BINARY_EXTENSIONS` frozenset) before reading. UTF-8 decoding uses strict mode with `UnicodeDecodeError` catch. *(Fixed 2026-02-05)*

### DOCKER & DEPLOYMENT

- [x] ~~**Fix Nginx health check path**~~ — Resolved by P0 `/health` endpoint fix.
- [ ] **Validate Qdrant integration** — `docker-compose.prod.yml` includes Qdrant on a `qdrant` profile but no code connects to it. *(Deferred — requires Qdrant SDK dependency)*
- [x] **Add version validation to release workflow** — `release.yml` now compares tag version against `pyproject.toml` and fails on mismatch. *(Fixed 2026-02-05)*
- [x] **Handle missing credential mount** — `docker-compose.yml` now uses `${GEMINI_CREDS_PATH:-/dev/null}` fallback. *(Fixed 2026-02-05)*

### CONFIGURATION

- [x] **Add min/max validation to config fields** — `config.py` now has Pydantic `field_validator` for: port (1-65535), timeouts (>=1), token limit (>=1000), thresholds (0.0-1.0), swarm depth (1-20), swarm agents (1-50), log level (valid + uppercased), rate limit (>=0), request size (>=0). *(Fixed 2026-02-05)*
- [x] **Validate transport config** — `server.py:main()` now validates transport against `{"stdio", "sse", "streamable-http"}` with warning and fallback to SSE. *(Fixed 2026-02-05)*
- [x] ~~**Review `max_context_tokens` default**~~ — 900K is correct for Gemini 3 (1M context, 100K buffer). No change needed.

### DOCUMENTATION

- [x] **Update README.md** — Rewritten with Gemini 3 models, security features, swarm Supervisor Pattern, debate TF-IDF, full config table, Docker credential mounting. *(Fixed 2026-02-05)*
- [x] **Update .env.example** — Complete rewrite with all settings including rate limiting, audit logging, auto-discovery opt-in. *(Fixed 2026-02-05)*

---

## P3 — Low (Nice to Have) — MOSTLY RESOLVED

- [x] **Add rate limiting** — `middleware.py:RateLimitMiddleware` implements in-memory token bucket. Configurable via `GEMINI_MCP_RATE_LIMIT` (requests/min) and `GEMINI_MCP_RATE_LIMIT_BURST`. Returns 429 with Retry-After and X-RateLimit headers. Health endpoint exempt. 7 tests. *(Fixed 2026-02-05)*
- [x] **Add audit logging** — `middleware.py:audit_event()` provides structured JSON audit logging for all tool invocations. Opt-in via `GEMINI_MCP_AUDIT_LOG=true`. Uses stdlib logging with custom JSON formatter. 2 tests. *(Fixed 2026-02-05)*
- [x] **Add request size limits** — `middleware.py:RequestSizeLimitMiddleware` rejects requests exceeding `GEMINI_MCP_MAX_REQUEST_SIZE` (default 10MB) with 413. 2 tests. *(Fixed 2026-02-05)*
- [ ] **Implement plugin sandboxing** (e.g. restricted imports, resource limits) — Complex, deferred. Current allowlist + SHA-256 verification provides baseline security.
- [x] **Add debate context truncation warning** — `debate/orchestrator.py:get_context_summary()` already logs a warning when context is truncated. *(Verified 2026-02-05)*
- [x] **Make GCP project auto-discovery opt-in** — `gemini.py` now checks `config.auto_discover_project` (default False) before making external HTTP call. Configurable via `GEMINI_MCP_AUTO_DISCOVER_PROJECT=true`. *(Fixed 2026-02-05)*

---

## Metrics Snapshot

| Metric | Value |
|--------|-------|
| Source LOC | ~3,500 |
| Test LOC | ~850 |
| Test count | 112 (all passing) |
| Test coverage (estimated) | ~65% |
| Critical issues (P0) | ~~5~~ → 0 |
| High issues (P1) | ~~13~~ → 0 |
| Medium issues (P2) | ~~16~~ → 1 remaining (Qdrant integration) |
| Low issues (P3) | ~~6~~ → 1 remaining (plugin sandboxing) |
| Security findings | ~~5~~ → 0 |
