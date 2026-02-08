# TODO — Gemini MCP v2

> Generated from comprehensive code analysis on 2026-02-05
> Updated with security/bug audit on 2026-02-08
> Round 3 cleanup on 2026-02-08 (MCP bump, CI scanning, P3 fixes, docs)

---

## P0 — Critical (Fix Before Any Deployment) — ALL RESOLVED

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

## P1 — High (Before Production Use) — ALL RESOLVED

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

### DEPENDENCIES (Round 2+3 — 2026-02-08) — ALL RESOLVED

- [x] **Bump `mcp` to `>=1.25.0,<2.0`** — Updated from `==1.23.0`. Pinned to v1.x for stability ahead of MCP SDK v2 (Q1 2026) which renames `FastMCP` → `MCPServer`. *(Fixed 2026-02-08)*
- [x] **Pin `google-genai` properly** — Changed `>=0.3.0` to `>=1.50.0,<2.0` to ensure Gemini 3 support and prevent breaking changes. *(Fixed 2026-02-08)*
- [x] **Bump `httpx` minimum** — Changed `>=0.25.0` to `>=0.27.0`. *(Fixed 2026-02-08)*

---

## P2 — Medium (Quality & Robustness) — ALL RESOLVED

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

### DOCKER & DEPLOYMENT (Round 1+3) — ALL RESOLVED

- [x] ~~**Fix Nginx health check path**~~ — Resolved by P0 `/health` endpoint fix.
- [x] **Validate Qdrant integration** — `docker-compose.prod.yml` Qdrant is correctly gated behind `profiles: [qdrant]` (opt-in). No code dependency needed until Qdrant client integration is implemented as a feature. *(Resolved 2026-02-08)*
- [x] **Add version validation to release workflow** *(Fixed 2026-02-05)*
- [x] **Handle missing credential mount** *(Fixed 2026-02-05)*

### CONFIGURATION (Round 1 — 2026-02-05) — ALL RESOLVED

- [x] **Add min/max validation to config fields** *(Fixed 2026-02-05)*
- [x] **Validate transport config** *(Fixed 2026-02-05)*
- [x] ~~**Review `max_context_tokens` default**~~ — 900K is correct for Gemini 3.

### DOCUMENTATION (Round 1+3 — 2026-02-08) — ALL RESOLVED

- [x] **Update README.md** — Added security scanning badge, middleware architecture diagram, rate limiting + internal limits config tables, MCP v2 migration note. *(Updated 2026-02-08)*
- [x] **Update .env.example** — Added `SWARM_MAX_TURNS`, `MAX_TRACE_FILES`, `MAX_DEBATE_FILES`, `RESULT_TRUNCATION_CHARS`. *(Updated 2026-02-08)*
- [x] **Update CHANGELOG.md** — Added v1.1.0 with complete security/fix/change log. *(Updated 2026-02-08)*
- [x] **Update SECURITY.md** — Added pure ASGI middleware, timing attack, ReDoS, thread safety, CI scanning. *(Updated 2026-02-08)*

### BUGS (Round 2+3 — 2026-02-08) — ALL RESOLVED

- [x] **Fix path validation bypass via inline code** — Reordered `analyze()` to check paths before inline code detection. *(Fixed 2026-02-08)*
- [x] **Fix unbounded file reading in directory analysis** — Now checks `file_path.stat().st_size` before reading. *(Fixed 2026-02-08)*
- [x] **Add bounds to JSON extraction parser** — `_extract_json_object()` now limits scan to 100K characters. *(Fixed 2026-02-08)*
- [x] **Fix unsafe regex in delegation parsing (ReDoS)** — Replaced `(.*?)` with `[^)]{1,2000}` + manual split. *(Fixed 2026-02-08)*
- [x] **Cap adjudication panel size** — Panel now capped at 10 personas. *(Fixed 2026-02-08)*
- [x] **Wrap progress callbacks in try/except** — All callbacks now wrapped with exception handling. *(Fixed 2026-02-08)*
- [x] **Fix plugin allowlist directory traversal** — Now checks `relative_to(plugin_path)`. *(Fixed 2026-02-08)*
- [x] **Fix async mission registry leak** — `_run_and_persist()` uses `finally` block. *(Fixed 2026-02-08)*
- [x] **Fix `get_by_name()` ValueError in delegation** — Wrapped in `try/except (ValueError, KeyError)`. *(Fixed 2026-02-08)*
- [x] **Fix non-thread-safe client singleton** — Double-checked locking with `threading.Lock`. *(Fixed 2026-02-08)*
- [x] **Add CI vulnerability scanning** — GitHub Actions workflow with Trivy (Docker image + filesystem) and pip-audit. *(Fixed 2026-02-08)*

---

## P3 — Low (Nice to Have)

### RESOLVED (Round 1 — 2026-02-05)

- [x] **Add rate limiting** *(Fixed 2026-02-05)*
- [x] **Add audit logging** *(Fixed 2026-02-05)*
- [x] **Add request size limits** *(Fixed 2026-02-05)*
- [x] **Add debate context truncation warning** *(Verified 2026-02-05)*
- [x] **Make GCP project auto-discovery opt-in** *(Fixed 2026-02-05)*

### RESOLVED (Round 2+3 — 2026-02-08)

- [x] **Make Bearer scheme case-insensitive** — per RFC 7235. *(Fixed 2026-02-08)*
- [x] **Fix empty completion parsing** — Returns `None` for empty strings. *(Fixed 2026-02-08)*
- [x] **Fix Docker HEALTHCHECK port variable** — Hardcoded port in health check to match EXPOSE directive (build-time `${GEMINI_MCP_SERVER_PORT}` doesn't resolve at runtime). *(Fixed 2026-02-08)*
- [x] **Move magic numbers to config** — `swarm_max_turns`, `max_trace_files`, `max_debate_files`, `result_truncation_chars` now configurable via `GEMINI_MCP_` env vars. *(Fixed 2026-02-08)*
- [x] **Validate debate strategy input** — Unknown strategy now returns error with valid options list instead of silently defaulting. *(Fixed 2026-02-08)*
- [x] **Add input length validation** — `objective`, `topic`, `context` parameters validated against `max_context_tokens * 4` chars. *(Fixed 2026-02-08)*

### OPEN (Future Enhancements)

- [ ] **Implement plugin sandboxing** (e.g. restricted imports, resource limits) — Complex, deferred. Current allowlist + SHA-256 verification provides baseline security.
- [ ] **Add HTTP integration tests** — All current tests use mocks. Need real HTTP client tests for auth, rate limiting, SSE transport.
- [ ] **Improve debate novelty for first round** — `debate/orchestrator.py:495`: first round always returns novelty=1.0, making convergence detection useless until round 3+. By design — `min_rounds` exists for this reason.
- [ ] **Add Qdrant client integration** — `docker-compose.prod.yml` includes Qdrant behind `profiles: [qdrant]`. Future: add `qdrant-client` dependency and vector search integration for knowledge storage.
- [ ] **MCP SDK v2 migration** — When MCP SDK v2 ships (Q1 2026), migrate `FastMCP` → `MCPServer`, move transport params from constructor to `run()`. Current pin `>=1.25.0,<2.0` ensures stability.

---

## Metrics Snapshot

| Metric | Value (2026-02-05) | Value (2026-02-08 R2) | Value (2026-02-08 R3) |
|--------|--------------------|-----------------------|-----------------------|
| Source LOC | ~3,500 | ~3,700 | ~3,800 |
| Test LOC | ~850 | ~860 | ~860 |
| Test count | 112 | 116 (all passing) | 116 (all passing) |
| Test coverage | ~65% | ~65% | ~65% |
| P0 issues | ~~5~~ → 0 | 5 → **0** | **0** |
| P1 issues | ~~13~~ → 0 | 9 → **1** | **0** |
| P2 issues | ~~16~~ → 1 | 12 → **2** | **0** |
| P3 issues | ~~6~~ → 1 | 9 → **7** | **5** (future enhancements) |
| Security findings | ~~5~~ → 0 | 8 → **0** | **0** |
| Dependencies outdated | — | 4 → **1** | **0** |
| CI workflows | 2 (ci, release) | 2 | **3** (+ security) |
