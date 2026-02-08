# Contributing to gemini-mcp

Thank you for your interest in contributing to gemini-mcp!

## Getting Started

1. **Open an issue first** for non-trivial changes. This lets us discuss the approach before you invest time coding.
2. Fork and clone the repository.
3. Create a feature branch from `main`.

## Development Setup

### Local Development

```bash
python -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows

pip install -e ".[dev]"
pre-commit install
```

### Docker Development (Recommended)

```bash
# Build the image
docker build -f docker/Dockerfile -t gemini-mcp:dev .

# Run tests inside Docker
docker run --rm gemini-mcp:dev pytest tests/ -v

# Run the server locally
cp .env.example .env
# Edit .env with your API key
docker compose up
```

## Project Structure

```
src/gemini_mcp/
  server.py            # Entry point — MCP server, tool registration, plugin loading, auth
  config.py            # All settings (pydantic-settings) with GEMINI_MCP_ prefix
  middleware.py         # Rate limiting, request size limits, audit logging
  core/
    gemini.py          # Gemini API client wrapper (google-genai SDK)
  tools/
    core.py            # Core tools: gemini(), analyze(), search() + path validation
  swarm/
    core.py            # SwarmOrchestrator — Supervisor Pattern delegation loop
    memory.py          # TraceStore (file locking, disk quota), SwarmRegistry, Blackboard
  debate/
    orchestrator.py    # DebateOrchestrator — TF-IDF novelty, JSON extraction, persistence
personas/              # Markdown persona definitions for swarm agents
plugins/               # Custom tool plugins (auto-loaded, allowlist-gated)
tests/                 # pytest test suite
docker/                # Dockerfile + production configs
examples/              # Usage examples
```

### Key Patterns

- **Configuration**: All settings in `config.py` via pydantic-settings. Every numeric/enum field has a validator. Prefix: `GEMINI_MCP_`.
- **Auth chain**: API key (`GOOGLE_API_KEY`) > OAuth credentials > Application Default Credentials.
- **Path safety**: `tools/core.py` validates all file paths against allowed roots, blocks `/etc`, `/proc`, `/sys`.
- **Plugin loading**: `server.py` scans `plugins/`, checks allowlist, optionally verifies SHA-256 hashes.
- **File locking**: Both TraceStore and DebateMemory use `filelock` with `.lock` sidecar files.
- **Disk quotas**: 500-file limit on traces and debates, oldest files pruned automatically.

## Running Tests

All tests use mocks — no API key required.

```bash
# Full test suite
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=src/gemini_mcp --cov-report=term-missing

# Single test file
pytest tests/test_config.py -v

# Run in Docker (avoids local Python conflicts)
docker build -f docker/Dockerfile -t gemini-mcp:test .
docker run --rm gemini-mcp:test pytest tests/ -v
```

### Testing Different Transports

```bash
# Test SSE transport
GEMINI_MCP_TRANSPORT=sse pytest tests/test_server.py -v

# Test with auth enabled
GEMINI_MCP_AUTH_TOKEN=test-token pytest tests/test_middleware.py -v
```

## Code Style

- **Formatter**: [Black](https://black.readthedocs.io/) (line length 100)
- **Linter**: [Ruff](https://docs.astral.sh/ruff/) (line length 100)
- **Type checker**: [MyPy](https://mypy.readthedocs.io/)
- **Style guide**: [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)

Run all checks before submitting:

```bash
black src/ tests/
ruff check src/ tests/
mypy src/ --ignore-missing-imports
pytest tests/ -v
```

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `refactor:` Code refactoring
- `test:` Test additions/changes
- `chore:` Maintenance tasks

Example: `feat: add support for custom model selection`

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes with clear commit messages
3. Add tests for new functionality
4. Update documentation as needed
5. Ensure all checks pass (formatting, linting, types, tests)
6. Submit a PR using the [PR template](.github/PULL_REQUEST_TEMPLATE.md)

## Adding New Tools

1. Implement your tool function in `src/gemini_mcp/tools/` or as a plugin in `plugins/`
2. Register it in `src/gemini_mcp/server.py` using `@mcp.tool()`
3. Add tests in `tests/`
4. Update `README.md` with usage examples
5. If it's a core tool (not a plugin), add it to the tools table in `GEMINI.md`

## Adding Personas

1. Create a markdown file in `personas/` (e.g., `personas/my_expert.md`)
2. Include sections: Role, Expertise, Capabilities, Tools, Guidelines
3. Test with the swarm system: `swarm(objective="...", agents=["my_expert"])`
4. See existing personas for format reference

## Security

- Never commit credentials, API keys, or secrets
- Use environment variables for all sensitive configuration
- Report security vulnerabilities via [SECURITY.md](SECURITY.md) — do NOT open public issues
- All file operations must respect path validation

## Questions?

- Open a [Discussion](https://github.com/alfredojrc/gemini-mcp/discussions) for questions
- Use [Issues](https://github.com/alfredojrc/gemini-mcp/issues) for bug reports and feature requests

Thank you for contributing!
