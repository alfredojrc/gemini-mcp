"""Core tools for Gemini MCP Server.

This module implements the primary tools:
- gemini: AI query interface
- analyze: Code and file analysis
- search: Web search with grounding
"""

import logging
import os
from pathlib import Path
from typing import Literal

from ..config import config
from ..core.gemini import GeminiRequest, get_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pre-flight token estimation.
#
# Uses a conservative 3.5 chars-per-token heuristic (typical for English
# prose with code).  This is intentionally cheap — no API call, no extra
# dependency.  The real token count comes back in the API response metadata
# and is logged there.
# ---------------------------------------------------------------------------
_CHARS_PER_TOKEN = 3.5  # conservative estimate for English + code


def _estimate_tokens(text: str, model: str | None = None) -> int:
    """Estimate token count from character length (heuristic)."""
    return int(len(text) / _CHARS_PER_TOKEN)


def _validate_prompt_tokens(prompt: str, model: str | None = None) -> str | None:
    """Return an error string if *prompt* exceeds the configured token limit.

    Returns None when the prompt is within budget.
    """
    estimate = _estimate_tokens(prompt, model)
    if estimate > config.max_context_tokens:
        return (
            f"Prompt too large: ~{estimate:,} estimated tokens exceeds the "
            f"{config.max_context_tokens:,}-token limit. "
            f"Please reduce the input size."
        )
    return None


# ---------------------------------------------------------------------------
# Path validation — prevent directory traversal outside allowed roots.
# Set GEMINI_MCP_ALLOWED_PATHS to a colon-separated list of base directories
# (e.g. "/home/app/projects:/tmp/analysis").
# When unset, defaults to CWD + /tmp.
# ---------------------------------------------------------------------------
_SENSITIVE_PATHS = frozenset(
    {
        "/etc",
        "/var",
        "/root",
        "/proc",
        "/sys",
        "/dev",
        "/boot",
        "/sbin",
        "/usr/sbin",
    }
)


def _get_allowed_roots() -> list[Path]:
    """Return resolved allowed base directories for path operations."""
    raw = os.getenv("GEMINI_MCP_ALLOWED_PATHS", "").strip()
    if raw:
        return [Path(p).resolve() for p in raw.split(":") if p.strip()]
    # Default: CWD + /tmp + home directory
    roots = [Path.cwd().resolve(), Path("/tmp").resolve()]
    home = Path.home().resolve()
    if home.exists():
        roots.append(home)
    return roots


def _validate_path(target: str) -> Path | str:
    """Validate a filesystem path against allowed roots.

    Returns the resolved Path if valid, or an error string if rejected.
    """
    try:
        resolved = Path(target).resolve()
    except (OSError, ValueError) as exc:
        return f"Invalid path: {exc}"

    # Block known sensitive system directories
    resolved_str = str(resolved)
    for sensitive in _SENSITIVE_PATHS:
        if resolved_str == sensitive or resolved_str.startswith(sensitive + "/"):
            return f"Access denied: {target} is in a restricted system directory"

    # Check against allowed roots
    allowed = _get_allowed_roots()
    for root in allowed:
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            continue

    allowed_str = ", ".join(str(r) for r in allowed)
    return (
        f"Access denied: {target} is outside allowed directories ({allowed_str}). "
        f"Set GEMINI_MCP_ALLOWED_PATHS to expand access."
    )


# =============================================================================
# Tool 1: gemini - Unified AI Query Interface
# =============================================================================
async def gemini(
    prompt: str,
    mode: Literal["fast", "reasoning", "explain", "summarize", "models"] = "fast",
    model: str | None = None,
    context: str = "",
) -> dict | str:
    """
    Query Gemini AI with various modes.

    Args:
        prompt: Your question or request
        mode: Query mode
            - fast: Quick response (default)
            - reasoning: Deep analysis with extended thinking
            - explain: Detailed explanation
            - summarize: Bullet point summary
            - models: List available models
        model: Optional model override
        context: Additional context

    Returns:
        Response text or dict with metadata
    """
    client = get_client()

    if mode == "models":
        return {
            "models": client.get_available_models(),
            "default_model": client.default_model,
            "fast_model": client.fast_model,
        }

    # Pre-flight token validation
    combined = f"{context}\n\n{prompt}" if context else prompt
    token_err = _validate_prompt_tokens(combined, model)
    if token_err:
        return {"error": token_err}

    # Build request based on mode
    if mode == "summarize":
        full_prompt = f"""Summarize the following content into key bullet points:

{prompt}

Format as a concise bulleted list (max 5 points)."""
        if context:
            full_prompt = f"{context}\n\n{full_prompt}"
        request = GeminiRequest(prompt=full_prompt, model=client.fast_model)

    elif mode == "explain":
        full_prompt = f"""Explain {prompt} for a developer audience.

Be thorough but concise. Include:
- Key concepts
- Practical examples
- Common pitfalls
- Best practices"""
        if context:
            full_prompt = f"{context}\n\n{full_prompt}"
        request = GeminiRequest(prompt=full_prompt, model=client.default_model)

    elif mode == "reasoning":
        full_prompt = f"""You are performing extended reasoning analysis.

Perform a thorough analysis:
1. Break down the problem into components
2. Consider multiple perspectives and hypotheses
3. Evaluate trade-offs and implications
4. Synthesize findings into clear conclusions

{f"Context: {context}" if context else ""}

Problem/Question:
{prompt}

Provide your analysis with clear reasoning steps."""
        request = GeminiRequest(
            prompt=full_prompt,
            model=client.default_model,
            timeout=config.reasoning_timeout,
        )

    else:  # fast mode
        target_model = model or client.fast_model
        full_prompt = f"Context:\n{context}\n\n{prompt}" if context else prompt
        request = GeminiRequest(prompt=full_prompt, model=target_model)

    # Execute request
    response = await client.generate(request)

    # Return format based on mode
    if mode == "reasoning" or model:
        return response.to_dict()

    return response.text


# =============================================================================
# Tool 2: analyze - Code and File Analysis
# =============================================================================
async def analyze(
    target: str,
    instruction: str,
    focus: Literal["general", "security", "performance", "architecture", "patterns"] = "general",
) -> dict | str:
    """
    Analyze code, files, or directories using Gemini's large context.

    Args:
        target: What to analyze - can be:
            - File path (e.g., "/path/to/file.py")
            - Directory path (e.g., "/path/to/src/")
            - Inline code snippet
            - Git diff (starts with "diff --git")
        instruction: What to analyze for
        focus: Analysis focus area

    Returns:
        Analysis results
    """
    # Detect target type
    is_likely_code = (
        "\n" in target
        or target.startswith("```")
        or target.startswith("def ")
        or target.startswith("class ")
        or target.startswith("import ")
        or target.startswith("from ")
        or target.startswith("async ")
        or target.startswith("const ")
        or target.startswith("function ")
        or len(target) > 4096
    )

    # Handle PR diff
    if target.startswith("diff --git") or "index " in target[:100]:
        return await _review_diff(target, instruction)

    # Handle inline code
    if is_likely_code:
        return await _review_code(target, instruction, focus)

    # Try as path — with traversal protection
    try:
        validated = _validate_path(target)
        if isinstance(validated, str):
            # validation returned an error message
            return {"error": validated}
        path = validated
        if path.is_dir():
            if focus == "architecture":
                return await _explain_architecture(str(path), instruction)
            return await _analyze_directory(str(path), instruction, focus)
        if path.is_file():
            return await _review_file(str(path), instruction, focus)
    except OSError:
        pass

    # Fallback: treat as code
    return await _review_code(target, instruction, focus)


async def _review_code(code: str, instruction: str, focus: str) -> str:
    """Review inline code snippet."""
    prompt = f"""Review this code with focus on {focus}:

```
{code}
```

Instruction: {instruction}

Provide:
1. Overall assessment
2. Critical issues (must fix)
3. Warnings (should fix)
4. Suggestions (nice to have)

Be specific with line references."""

    client = get_client()
    request = GeminiRequest(prompt=prompt, model=client.default_model)
    response = await client.generate(request)
    return response.text


_BINARY_EXTENSIONS = frozenset(
    {
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bin",
        ".dat",
        ".db",
        ".sqlite",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".webp",
        ".svg",
        ".mp3",
        ".mp4",
        ".avi",
        ".mov",
        ".wav",
        ".flac",
        ".ogg",
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".7z",
        ".rar",
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".pyc",
        ".pyo",
        ".class",
        ".o",
        ".a",
        ".whl",
        ".egg",
        ".wasm",
        ".ttf",
        ".otf",
        ".woff",
        ".woff2",
        ".eot",
    }
)


async def _review_file(file_path: str, instruction: str, focus: str) -> dict:
    """Review a file from filesystem."""
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    # Skip binary files instead of silently corrupting them with errors="replace"
    if path.suffix.lower() in _BINARY_EXTENSIONS:
        return {"error": f"Cannot analyze binary file: {path.name}"}

    try:
        content = path.read_text(encoding="utf-8")
        if len(content) > 100000:
            content = content[:100000] + "\n...[TRUNCATED]..."
    except UnicodeDecodeError:
        return {"error": f"File appears to be binary (not UTF-8): {path.name}"}
    except Exception as e:
        return {"error": f"Failed to read file: {e}"}

    prompt = f"""Review this file with focus on {focus}.

File: {path.name}
Instruction: {instruction}

```
{content}
```

Provide specific findings with line numbers."""

    # Pre-flight token check
    token_err = _validate_prompt_tokens(prompt)
    if token_err:
        return {"error": token_err}

    client = get_client()
    request = GeminiRequest(prompt=prompt, model=client.default_model)
    response = await client.generate(request)

    return {
        "file": str(path),
        "focus": focus,
        "review": response.text,
        "elapsed_seconds": response.elapsed_seconds,
    }


async def _review_diff(diff: str, instruction: str) -> dict:
    """Review a PR diff."""
    prompt = f"""Review this pull request diff:

Instruction: {instruction}

```diff
{diff}
```

Provide:
1. Summary of changes
2. Critical issues (blocking)
3. Suggestions (non-blocking)
4. Security implications
5. Approval recommendation (APPROVE/REQUEST_CHANGES/COMMENT)"""

    client = get_client()
    request = GeminiRequest(prompt=prompt, model=client.default_model)
    response = await client.generate(request)

    return {
        "review": response.text,
        "elapsed_seconds": response.elapsed_seconds,
    }


async def _analyze_directory(directory: str, instruction: str, focus: str) -> dict:
    """Analyze a directory of code."""
    path = Path(directory)
    if not path.exists():
        return {"error": f"Directory not found: {directory}"}

    # Collect file contents
    exclude_dirs = {
        "tests",
        "test",
        "__pycache__",
        ".git",
        ".venv",
        "node_modules",
        ".pytest_cache",
        "dist",
        "build",
    }

    files_content = []
    total_size = 0
    max_size = 500000  # 500KB limit

    for file_path in path.rglob("*"):
        if file_path.is_file() and not any(p in file_path.parts for p in exclude_dirs):
            if file_path.suffix in {".py", ".js", ".ts", ".go", ".rs", ".java", ".md"}:
                try:
                    content = file_path.read_text(encoding="utf-8")
                    if total_size + len(content) > max_size:
                        break
                    files_content.append(
                        f"### {file_path.relative_to(path)}\n```\n{content[:10000]}\n```"
                    )
                    total_size += len(content)
                except Exception:
                    pass

    if not files_content:
        return {"error": "No analyzable files found in directory"}

    prompt = f"""Analyze this codebase with focus on {focus}.

Instruction: {instruction}

{chr(10).join(files_content)}

Provide comprehensive analysis referencing specific files."""

    # Pre-flight token check
    token_err = _validate_prompt_tokens(prompt)
    if token_err:
        return {"error": token_err}

    client = get_client()
    request = GeminiRequest(
        prompt=prompt, model=client.default_model, timeout=config.activity_timeout
    )
    response = await client.generate(request)

    return {
        "directory": str(path),
        "focus": focus,
        "files_analyzed": len(files_content),
        "analysis": response.text,
        "elapsed_seconds": response.elapsed_seconds,
    }


async def _explain_architecture(directory: str, instruction: str) -> dict:
    """Generate architecture explanation."""
    path = Path(directory)
    if not path.exists():
        return {"error": f"Directory not found: {directory}"}

    # List directory structure
    structure = []
    for item in sorted(path.iterdir()):
        if item.name.startswith("."):
            continue
        if item.is_dir():
            structure.append(f"  {item.name}/")
        else:
            structure.append(f"  {item.name}")

    prompt = f"""Analyze this codebase and generate architecture documentation.

Directory: {path.name}
Structure:
{chr(10).join(structure)}

Instruction: {instruction}

Include:
1. System overview
2. Component diagram (text-based)
3. Data flow
4. Key design patterns
5. Technology choices
6. Areas for improvement"""

    client = get_client()
    request = GeminiRequest(
        prompt=prompt, model=client.default_model, timeout=config.activity_timeout
    )
    response = await client.generate(request)

    return {
        "directory": str(path),
        "architecture": response.text,
        "elapsed_seconds": response.elapsed_seconds,
    }


# =============================================================================
# Tool 3: search - Web Search
# =============================================================================
async def search(
    query: str,
    depth: Literal["quick", "deep", "academic", "docs"] = "quick",
    topic_context: str | None = None,
) -> dict:
    """
    Search the web using Gemini's Google Search grounding.

    Args:
        query: What to search for
        depth: Search depth
            - quick: Single web search (default)
            - deep: Comprehensive research
            - academic: Academic sources
            - docs: Library documentation
        topic_context: Additional context

    Returns:
        Search results with sources
    """
    if depth == "docs":
        return await _search_docs(query, topic_context or "")
    if depth == "academic":
        return await _search_academic(query)
    if depth == "deep":
        return await _search_deep(query, topic_context)
    return await _search_quick(query, topic_context or "")


async def _search_quick(query: str, context: str) -> dict:
    """Quick web search."""
    prompt = f"""Search the web for current information about: {query}

{f"Context: {context}" if context else ""}

Provide:
1. Direct answer to the query
2. Key findings with sources
3. Recent developments
4. Relevant data

Cite sources where possible."""

    client = get_client()
    request = GeminiRequest(prompt=prompt, model=client.default_model)
    response = await client.generate(request)

    return {
        "query": query,
        "depth": "quick",
        "results": response.text,
        "elapsed_seconds": response.elapsed_seconds,
    }


async def _search_deep(query: str, context: str | None) -> dict:
    """Deep comprehensive research."""
    prompt = f"""Comprehensive research on: {query}

{f"Context: {context}" if context else ""}

Use web search to find current information.

Structure your research:
1. Executive Summary
2. Key Concepts
3. Current State
4. Recent Developments
5. Best Practices
6. Challenges & Considerations
7. Resources & References"""

    client = get_client()
    request = GeminiRequest(
        prompt=prompt,
        model=client.default_model,
        timeout=config.reasoning_timeout,
    )
    response = await client.generate(request)

    return {
        "query": query,
        "depth": "deep",
        "research": response.text,
        "elapsed_seconds": response.elapsed_seconds,
    }


async def _search_academic(query: str) -> dict:
    """Academic paper search."""
    prompt = f"""Research academic papers and scholarly sources about: {query}

Provide:
1. Key academic findings
2. Methodology overview
3. Practical applications
4. Limitations noted in research
5. Recent developments
6. Recommended papers/resources

Use Google Scholar and academic sources."""

    client = get_client()
    request = GeminiRequest(
        prompt=prompt,
        model=client.default_model,
        timeout=config.reasoning_timeout,
    )
    response = await client.generate(request)

    return {
        "query": query,
        "depth": "academic",
        "research": response.text,
        "elapsed_seconds": response.elapsed_seconds,
    }


async def _search_docs(library: str, topic: str) -> dict:
    """Library documentation search."""
    prompt = f"""Find documentation for {library}.
{f"Specific topic: {topic}" if topic else ""}

Provide:
1. Installation instructions
2. Basic usage
3. Key APIs/functions
4. Common patterns
5. Gotchas and tips

Search for official documentation and examples."""

    client = get_client()
    request = GeminiRequest(prompt=prompt, model=client.default_model)
    response = await client.generate(request)

    return {
        "library": library,
        "topic": topic,
        "depth": "docs",
        "documentation": response.text,
        "elapsed_seconds": response.elapsed_seconds,
    }
