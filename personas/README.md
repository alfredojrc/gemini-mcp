# Custom Personas

Place custom persona definitions here. The swarm system can load these to create specialized agents.

## Persona Format

Each persona is a Markdown file with the following structure:

```markdown
# Persona Name

## Role
Brief description of the persona's role.

## Expertise
- Expertise area 1
- Expertise area 2

## Capabilities
What this persona can do.

## Tools
Which tools this persona should use:
- analyze
- search
- etc.

## Guidelines
How this persona should behave.
```

## Example Personas

- `security_expert.md` - Security and vulnerability specialist
- `devops_engineer.md` - Infrastructure and deployment specialist

## Using Custom Personas

Custom personas can be referenced in swarm operations:

```python
swarm(
    objective="Audit security of authentication system",
    agents=["architect", "security_expert"]
)
```

The swarm system will load the persona definition and configure the agent accordingly.
