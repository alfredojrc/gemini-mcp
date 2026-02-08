# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in gemini-mcp, please report it responsibly.

### How to Report

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please use one of these methods:

1. **GitHub Security Advisories** (preferred): Go to the [Security tab](https://github.com/alfredojrc/gemini-mcp/security/advisories/new) and create a private advisory.
2. **Email**: Send details to the repository maintainer via the email listed on their GitHub profile.

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Affected versions
- Potential impact
- Suggested fix (if any)

### Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial assessment**: Within 1 week
- **Fix release**: Within 2 weeks for critical issues

### Scope

The following are in scope for security reports:

- Authentication bypass (bearer token, API key handling)
- Path traversal in the `analyze` tool (escaping allowed directories)
- Plugin system sandbox escapes
- Secrets leakage in logs or error messages
- Rate limiting bypass
- Server-side request forgery (SSRF)
- Denial of service via crafted MCP requests

### Out of Scope

- Vulnerabilities in upstream dependencies (report to those projects directly)
- Issues requiring physical access to the host
- Social engineering attacks
- Vulnerabilities in the Gemini API itself (report to Google)

### Security Design

gemini-mcp implements defense in depth:

- **Authentication**: Optional bearer token for HTTP transports (`GEMINI_MCP_AUTH_TOKEN`) with constant-time comparison (`hmac.compare_digest`) and RFC 7235-compliant case-insensitive scheme parsing
- **Pure ASGI middleware**: All middleware (auth, rate limit, size limit) uses raw ASGI protocol — no `BaseHTTPMiddleware` to avoid SSE streaming buffer, background task blocking, and ContextVar issues
- **Path validation**: File analysis restricted to configured allowed paths; blocks `/etc`, `/proc`, `/sys`, `/dev`, `/boot`; validates path before inline code detection
- **Plugin sandboxing**: Allowlist with relative path validation (`relative_to()`) + SHA-256 hash verification
- **Rate limiting**: Per-IP token bucket with LRU eviction (10K bucket cap) preventing memory exhaustion from rotating-IP attacks
- **Request size limits**: Configurable max body size (default 10MB) with chunked transfer encoding support
- **Input length validation**: All tool inputs validated against `max_context_tokens * 4` to prevent memory exhaustion in TF-IDF tokenization
- **ReDoS prevention**: LLM output parsing uses bounded character classes (`[^)]{1,2000}`) and 100K char scan limits
- **Thread safety**: Client singleton uses double-checked locking; TraceStore quota uses `threading.Lock`
- **Audit logging**: Optional structured JSON logging of all tool invocations
- **CI security scanning**: Trivy (Docker image + filesystem) and pip-audit in GitHub Actions
- **No secrets in code**: All credentials via environment variables; `.env` excluded from version control

### Acknowledgments

We appreciate responsible disclosure and will credit reporters in the release notes (unless anonymity is preferred).
