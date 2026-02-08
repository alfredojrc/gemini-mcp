# Custom Personas

Custom persona definitions that extend the swarm system with specialized agents. These are loaded automatically on server startup.

## Included Personas

| Persona | File | Specialization |
|---------|------|----------------|
| Security Expert | `security_expert.md` | Vulnerability assessment, threat modeling, secure code review |
| DevOps Engineer | `devops_engineer.md` | Infrastructure automation, CI/CD, observability |
| Codebase Investigator | `codebase_investigator.md` | Root cause analysis, dependency tracing, debugging |
| Code Reviewer | `code_reviewer.md` | Code correctness, edge cases, maintainability |
| Systems Engineer | `systems_engineer.md` | Performance optimization, low-latency, concurrency |

## Persona Format

Each persona is a Markdown file with these sections:

```markdown
# Persona Name

## Role
Brief description of the persona's role and approach.

## Expertise
- Area 1
- Area 2

## Capabilities
What this persona can do.

## Tools
Which tools this persona uses:
- analyze
- search
- complete

## Guidelines
How this persona should behave (numbered directives).
```

### Sections

| Section | Required | Purpose |
|---------|----------|---------|
| `# Title` | Yes | Agent display name |
| `## Role` | Yes | Injected as identity in the system prompt |
| `## Expertise` | No | Domain knowledge areas |
| `## Capabilities` | No | What the agent can do |
| `## Tools` | No | Available tools (defaults to `analyze`, `complete`) |
| `## Guidelines` | No | Behavioral directives |

## Using Custom Personas

Reference persona file names (without `.md`) in swarm operations:

```python
# Use in a swarm mission
swarm(
    objective="Audit the authentication system",
    agents=["architect", "security_expert", "code_reviewer"]
)

# Use in adjudication panel
swarm_adjudicate(
    query="Should we use JWT or session tokens?",
    panel=["security_expert", "systems_engineer", "architect"]
)
```

## Adding Your Own

1. Create a `.md` file in this directory following the format above
2. Restart the server — personas are loaded on startup
3. Reference by filename (e.g., `my_persona.md` becomes `my_persona`)
4. Optionally set `GEMINI_MCP_PERSONAS_DIR` to load from a different directory
