# Examples

This directory contains example scripts and configurations for using gemini-mcp.

## Basic Usage

### Python Script

```python
"""Example: Using gemini-mcp tools programmatically."""

import asyncio
from gemini_mcp.tools.core import gemini, analyze, search

async def main():
    # Simple query
    result = await gemini(
        prompt="Explain Python decorators",
        mode="explain"
    )
    print(result)

    # Code analysis
    code = '''
    def greet(name):
        return f"Hello, {name}!"
    '''
    analysis = await analyze(
        target=code,
        instruction="Review for best practices",
        focus="general"
    )
    print(analysis)

    # Web search
    results = await search(
        query="Python 3.12 new features",
        depth="quick"
    )
    print(results)

if __name__ == "__main__":
    asyncio.run(main())
```

### MCP Client Configuration

**For Gemini CLI** (`~/.gemini/settings.json`):
```json
{
  "mcpServers": {
    "gemini-mcp": {
      "url": "http://localhost:8765/sse"
    }
  }
}
```

**For Claude Code**:
```bash
claude mcp add gemini-mcp http://localhost:8765/sse --transport sse
```

## Swarm Examples

### Simple Mission

```python
from gemini_mcp.tools.swarm_tools import swarm_execute

result = await swarm_execute(
    objective="Design a REST API for a blog platform",
    mode="fast"
)
print(result)
```

### Multi-Agent Mission

```python
result = await swarm_execute(
    objective="Review and improve the authentication system",
    mode="thorough",
    agents=["architect", "security_expert", "reviewer"]
)
print(result)
```

### Expert Panel

```python
from gemini_mcp.tools.swarm_tools import swarm_adjudicate

result = await swarm_adjudicate(
    query="Should we use microservices or a monolith for our startup?",
    panel=["architect", "analyst", "devops_engineer"],
    strategy="supreme_court"
)
print(result["verdict"])
```

## Debate Examples

### Start a Debate

```python
from gemini_mcp.tools.debate_tools import debate

result = await debate(
    topic="Is TDD always the best approach?",
    action="start",
    strategy="adversarial"
)
print(result["synthesis"])
```

### Search Past Debates

```python
result = await debate(
    topic="testing strategies",
    action="search"
)
for r in result["results"]:
    print(f"- {r['topic']} (relevance: {r['relevance']})")
```

## Plugin Example

Create `plugins/my_tool.py`:

```python
"""Custom tool plugin."""

from gemini_mcp.server import mcp
from gemini_mcp.core.gemini import GeminiRequest, get_client

@mcp.tool()
async def my_custom_tool(input_text: str) -> str:
    """My custom AI tool.

    Args:
        input_text: Text to process

    Returns:
        Processed result
    """
    client = get_client()
    request = GeminiRequest(
        prompt=f"Process this: {input_text}",
        model=client.fast_model
    )
    response = await client.generate(request)
    return response.text
```

The plugin will be automatically loaded when the server starts.

## Docker Examples

### Basic Docker Compose

```yaml
services:
  gemini-mcp:
    build: .
    ports:
      - "8765:8765"
    environment:
      - GEMINI_MCP_TRANSPORT=sse
    volumes:
      - ~/.gemini:/home/app/.gemini:ro
```

### With Nginx Proxy

See `docker-compose.prod.yml` for a production-ready configuration with:
- Nginx reverse proxy for connection resilience
- Health checks
- Resource limits
- Persistent volumes
