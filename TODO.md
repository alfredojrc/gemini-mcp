# TODO — Gemini MCP v2

> Generated from comprehensive code analysis on 2026-02-05
> Updated with security/bug audit on 2026-02-08

---

## P0 — Critical (Fix Before Any Deployment)

### SECURITY (Round 1 — 2026-02-05) — ALL RESOLVED

- [x] **Sandbox plugin loader** — `server.py` now validates plugins against an optional allowlist (`GEMINI_MCP_PLUGIN_ALLOWLIST`) and SHA-256 sidecar verification (`GEMINI_MCP_PLUGIN_REQUIRE_HASH`). *(Fixed 2026-02-05)*
- [x] **Add path validation to `analyze()`** — `tools/core.py` now validates all paths against allowed roots (`GEMINI_MCP_ALLOWED_PATHS`) and blocks sensitive system directories (`/etc`, `/proc`, `/sys`, etc.). *(Fixed 2026-02-05)*
- [x] **Add authentication middleware** — Optional bearer-token auth via `GEMINI_MCP_AUTH_TOKEN` env var. When set, all HTTP requests require `Authorization: Bearer <token>`. Health endpoint exempt for Docker probes. *(Fixed 2026-02-05)*

### BUGS (Round 1 — 2026-02-05) — ALL RESOLVED

- [x] ~~**Fix default model names**~~ — **FALSE POSITIVE**: `gemini-3-pro-preview` and `gemini-3-flash-preview` are valid current Gemini 3 preview model IDs (confirmed Feb 2026). No change needed.
- [x] **Add `/health` endpoint** — Added via `@mcp.custom_route("/health")` using FastMCP's official custom-route API. Docker health checks now work. *(Fixed 2026-02-05)*

### SECURITY (Round 2 — 2026-02-08) — ALL RESOLVED

- [x] **Migrate `BaseHTTPMiddleware` to pure ASGI middleware** — All 3 middleware classes rewritten as pure ASGI using `__call__(scope, receive, send)`. Eliminates SSE streaming buffer, background task blocking, and ContextVar propagation issues. *(Fixed 2026-02-08)*
- [x] **Fix timing attack in Bearer token comparison** — `BearerAuthMiddleware` now uses `hmac.compare_digest()` for constant-time comparison. *(Fixed 2026-02-08)*
- [x] **Fix `filelock` CVE-2026-22701** — Bumped dependency pin from `>=3.13.0` to `>=3.20.3`. *(Fixed 2026-02-08)*

### BUGS (Round 2 — 2026-02-08) — ALL RESOLVED

- [x] **Guard `self.client` against None before API calls** — `generate()` and `stream()` now raise `GeminiAPIError` if client is None instead of crashing with `AttributeError`. *(Fixed 2026-02-08)*
- [x] **Fix rate limiter unbounded memory growth** — Replaced `defaultdict` with bounded dict + LRU eviction (`_MAX_RATE_LIMIT_BUCKETS = 10,000`). Oldest bucket evicted when at capacity. *(Fixed 2026-02-08)*

---

## P1 — High (Before Production Use)

### SWARM (Round 1 — 2026-02-05) — ALL RESOLVED

- [x] **Implement multi-agent delegation loop** — `swarm/core.py` now implements Supervisor Pattern. *(Fixed 2026-02-05)*
- [x] **Add mission timeout** — `swarm/core.py:_run_mission()` enforces `config.activity_timeout` hard ceiling per mission. *(Fixed 2026-02-05)*
- [x] **Store async mission results** — `swarm/core.py:_run_and_persist()` wrapper persists results for background missions. *(Fixed 2026-02-05)*
- [x] **Fix hardcoded confidence** — Parses confidence from each expert's JSON response. *(Fixed 2026-02-05)*
- [x] **Enforce safety protocols** — Turn limit bounded by `min(_MAX_TURNS, max_depth * 4)`. *(Fixed 2026-02-05)*

### DEBATE (Round 1 — 2026-02-05) — ALL RESOLVED

- [x] **Use distinct models/temperatures for experts** *(Fixed 2026-02-05)*
- [x] **Fix novelty metric** — TF-IDF cosine similarity. *(Fixed 2026-02-05)*
- [x] **Fix config attribute reference** *(Fixed 2026-02-05)*

### VALIDATION (Round 1 — 2026-02-05) — ALL RESOLVED

- [x] **Add context window check** *(Fixed 2026-02-05)*
- [x] **Add prompt size limits** *(Fixed 2026-02-05)*

### DATA INTEGRITY (Round 1 — 2026-02-05) — ALL RESOLVED

- [x] **Add file locking to TraceStore** *(Fixed 2026-02-05)*
- [x] **Add disk quota for traces** *(Fixed 2026-02-05)*
- [x] **Add disk quota for debates** *(Fixed 2026-02-05)*

### BUGS (Round 2 — 2026-02-08) — ALL RESOLVED

- [x] **Add timeout enforcement to agent delegation** — Each sub-agent now uses `asyncio.wait_for()` with remaining mission time budget instead of unlimited timeout. *(Fixed 2026-02-08)*
- [x] **Fix request size limit bypass via chunked encoding** — `RequestSizeLimitMiddleware` now wraps `receive()` to count streamed body bytes, rejecting oversized chunked bodies with 413. *(Fixed 2026-02-08)*
- [x] **Fix TraceStore quota race condition** — `_enforce_quota()` now protected by `threading.Lock` to prevent concurrent prune operations from deleting wrong files. *(Fixed 2026-02-08)*
- [x] **Fix lock timeout fallback** — On lock timeout, `save()` now logs error and skips the write instead of writing without lock (which risked corruption). *(Fixed 2026-02-08)*
- [x] **Fix bare `except: pass` in directory analysis** — Now logs `logger.debug(f"Skipping file {file_path}: {e}")` instead of silently swallowing all exceptions. *(Fixed 2026-02-08)*
- [x] **Add token validation to all API code paths** — `_review_code()`, `_review_diff()`, `_search_quick()`, `_search_deep()`, `_search_academic()`, `_search_docs()`, `_explain_architecture()` all now call `_validate_prompt_tokens()`. *(Fixed 2026-02-08)*

### DEPENDENCIES (Round 2 — 2026-02-08) — PARTIALLY RESOLVED

- [ ] **Bump `mcp==1.23.0` to `mcp==1.26.0`** — 3 versions behind, bugfixes only, no breaking changes. Prepare for MCP SDK v2 (Q1 2026) renaming `FastMCP` → `MCPServer`. *(Deferred — needs integration testing)*
- [x] **Pin `google-genai` properly** — Changed `>=0.3.0` to `>=1.50.0,<2.0` to ensure Gemini 3 support and prevent breaking changes. *(Fixed 2026-02-08)*
- [x] **Bump `httpx` minimum** — Changed `>=0.25.0` to `>=0.27.0`. *(Fixed 2026-02-08)*

---

## P2 — Medium (Quality & Robustness)

### TESTING (Round 1 — 2026-02-05) — ALL RESOLVED

- [x] **Add swarm orchestrator tests** *(Fixed 2026-02-05)*
- [x] **Add debate orchestrator tests** *(Fixed 2026-02-05)*
- [x] **Add plugin loader tests** *(Fixed 2026-02-05)*
- [x] **Add auth chain tests** *(Fixed 2026-02-05)*
- [x] **Add error-path tests** *(Fixed 2026-02-05)*
- [x] **Add config validation tests** *(Fixed 2026-02-05)*

### CODE QUALITY (Round 1 — 2026-02-05) — ALL RESOLVED

- [x] **Remove redundant execution modes** *(Fixed 2026-02-05)*
- [x] **Fix JSON regex parsing** *(Fixed 2026-02-05)*
- [x] **Fix `list_recent()` JSON error handling** *(Verified 2026-02-05)*
- [x] **Validate debate_id format** *(Fixed 2026-02-05)*
- [x] ~~**Replace naive relevance scoring**~~ *(Resolved 2026-02-05)*
- [x] **Handle encoding errors explicitly** *(Fixed 2026-02-05)*

### DOCKER & DEPLOYMENT (Round 1)

- [x] ~~**Fix Nginx health check path**~~ — Resolved by P0 `/health` endpoint fix.
- [ ] **Validate Qdrant integration** — `docker-compose.prod.yml` includes Qdrant but no code connects to it. *(Deferred — requires Qdrant SDK dependency)*
- [x] **Add version validation to release workflow** *(Fixed 2026-02-05)*
- [x] **Handle missing credential mount** *(Fixed 2026-02-05)*

### CONFIGURATION (Round 1 — 2026-02-05) — ALL RESOLVED

- [x] **Add min/max validation to config fields** *(Fixed 2026-02-05)*
- [x] **Validate transport config** *(Fixed 2026-02-05)*
- [x] ~~**Review `max_context_tokens` default**~~ — 900K is correct for Gemini 3.

### DOCUMENTATION (Round 1 — 2026-02-05) — ALL RESOLVED

- [x] **Update README.md** *(Fixed 2026-02-05)*
- [x] **Update .env.example** *(Fixed 2026-02-05)*

### BUGS (Round 2 — 2026-02-08) — MOSTLY RESOLVED

- [x] **Fix path validation bypass via inline code** — Reordered `analyze()` to check paths before inline code detection. Single-line non-code inputs are now validated as paths first, preventing newline injection bypass. *(Fixed 2026-02-08)*
- [x] **Fix unbounded file reading in directory analysis** — Now checks `file_path.stat().st_size` before reading. Large files are skipped with debug logging. *(Fixed 2026-02-08)*
- [x] **Add bounds to JSON extraction parser** — `_extract_json_object()` now limits scan to 100K characters to prevent CPU exhaustion on malformed input. *(Fixed 2026-02-08)*
- [x] **Fix unsafe regex in delegation parsing (ReDoS)** — Replaced `(.*?)` with `[^)]{1,2000}` character class + manual split. Prevents catastrophic backtracking. *(Fixed 2026-02-08)*
- [x] **Cap adjudication panel size** — Panel now capped at 10 personas. Excess personas logged and truncated. *(Fixed 2026-02-08)*
- [x] **Wrap progress callbacks in try/except** — All progress callbacks in swarm and debate orchestrators now wrapped with exception handling. Callback failures logged but don't crash missions. *(Fixed 2026-02-08)*
- [x] **Fix plugin allowlist directory traversal** — Now checks `plugin_file.relative_to(plugin_path)` instead of just `plugin_file.name`. *(Fixed 2026-02-08)*
- [x] **Fix async mission registry leak** — `_run_and_persist()` now uses `finally` block to ensure `unregister()` runs even on cancellation. *(Fixed 2026-02-08)*
- [x] **Fix `get_by_name()` ValueError in delegation** — Custom persona lookup now wrapped in `try/except (ValueError, KeyError)`. *(Fixed 2026-02-08)*
- [x] **Fix non-thread-safe client singleton** — `get_client()` now uses double-checked locking with `threading.Lock`. *(Fixed 2026-02-08)*
- [ ] **Add CI vulnerability scanning** — No `trivy`, `safety`, or `docker scan` in CI pipeline. Add dependency + container security scanning.

---

## P3 — Low (Nice to Have)

### RESOLVED (Round 1 — 2026-02-05)

- [x] **Add rate limiting** *(Fixed 2026-02-05)*
- [x] **Add audit logging** *(Fixed 2026-02-05)*
- [x] **Add request size limits** *(Fixed 2026-02-05)*
- [x] **Add debate context truncation warning** *(Verified 2026-02-05)*
- [x] **Make GCP project auto-discovery opt-in** *(Fixed 2026-02-05)*

### RESOLVED (Round 2 — 2026-02-08)

- [x] **Make Bearer scheme case-insensitive** — `BearerAuthMiddleware` now uses `auth_header[:7].lower() == "bearer "` per RFC 7235. *(Fixed 2026-02-08)*
- [x] **Fix empty completion parsing** — `_parse_completion()` now returns `None` for empty strings instead of `""`. *(Fixed 2026-02-08)*

### OPEN

- [ ] **Implement plugin sandboxing** (e.g. restricted imports, resource limits) — Complex, deferred. Current allowlist + SHA-256 verification provides baseline security.
- [ ] **Fix Docker HEALTHCHECK port variable** — `Dockerfile:57`: uses build-time `${GEMINI_MCP_SERVER_PORT}`, fails if overridden at runtime.
- [ ] **Move magic numbers to config** — `_MAX_TURNS=10`, `_MAX_TRACE_FILES=500`, `_MAX_DEBATE_FILES=500`, result truncation 2000 chars — should be configurable.
- [ ] **Add HTTP integration tests** — All current tests use mocks. Need real HTTP client tests for auth, rate limiting, SSE transport.
- [ ] **Improve debate novelty for first round** — `debate/orchestrator.py:495`: first round always returns novelty=1.0, making convergence detection useless until round 3+.
- [ ] **Validate debate strategy input** — `debate_tools.py:98`: invalid strategy silently defaults to COLLABORATIVE with no user feedback.
- [ ] **Add input length validation** — No length limits on `objective`, `topic`, `context` parameters. Very long inputs can exhaust memory in TF-IDF tokenization.

---

## Metrics Snapshot

| Metric | Value (2026-02-05) | Value (2026-02-08) |
|--------|--------------------|---------------------|
| Source LOC | ~3,500 | ~3,700 |
| Test LOC | ~850 | ~860 |
| Test count | 112 | 116 (all passing) |
| Test coverage | ~65% | ~65% |
| P0 issues | ~~5~~ → 0 | 5 → **0** |
| P1 issues | ~~13~~ → 0 | 9 → **1** (mcp bump deferred) |
| P2 issues | ~~16~~ → 1 | 12 → **2** (Qdrant, CI scanning) |
| P3 issues | ~~6~~ → 1 | 9 → **7** |
| Security findings | ~~5~~ → 0 | 8 → **0** |
| Dependencies outdated | — | 4 → **1** (mcp only) |
