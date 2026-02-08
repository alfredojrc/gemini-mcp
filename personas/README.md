# Custom Personas

A library of specialized agent personas for the swarm system. Loaded automatically on server startup. Use them in `swarm()` and `swarm_adjudicate()` calls.

## Persona Catalog

### Security & Compliance
| Persona | File | Specialization |
|---------|------|----------------|
| Security Expert | `security_expert.md` | Vulnerability assessment, OWASP, secure code review |
| Penetration Tester | `pentester.md` | Ethical hacking, attack simulation, exploit PoCs |
| Threat Modeler | `threat_modeler.md` | STRIDE/PASTA analysis, trust boundaries, risk rating |
| Compliance Analyst | `compliance_analyst.md` | GDPR, SOC 2, HIPAA, regulatory controls mapping |

### Engineering & Architecture
| Persona | File | Specialization |
|---------|------|----------------|
| Systems Engineer | `systems_engineer.md` | Low-latency, concurrency, memory optimization |
| Cloud Architect | `cloud_architect.md` | Multi-cloud, serverless, cost optimization, DR |
| Frontend Architect | `frontend_architect.md` | React/Vue/Angular, Web Vitals, accessibility |
| API Designer | `api_designer.md` | REST, GraphQL, gRPC, API versioning |
| Database Expert | `database_expert.md` | SQL/NoSQL, query optimization, schema design |
| Mobile Developer | `mobile_developer.md` | iOS, Android, cross-platform, offline-first |
| Blockchain Developer | `blockchain_developer.md` | Smart contracts, DeFi, gas optimization |

### Operations & Reliability
| Persona | File | Specialization |
|---------|------|----------------|
| DevOps Engineer | `devops_engineer.md` | CI/CD, IaC, container orchestration |
| SRE Engineer | `sre_engineer.md` | SLOs, incident response, chaos engineering |
| Performance Engineer | `performance_engineer.md` | Profiling, load testing, bottleneck elimination |

### Data & ML
| Persona | File | Specialization |
|---------|------|----------------|
| Data Scientist | `data_scientist.md` | Statistics, ML model selection, experimentation |
| ML Engineer | `ml_engineer.md` | MLOps, model serving, distributed training |
| Data Engineer | `data_engineer.md` | Pipelines, warehousing, stream processing |

### Finance & Trading
| Persona | File | Specialization |
|---------|------|----------------|
| Quantitative Analyst | `quant_analyst.md` | Signal discovery, risk modeling, backtesting |
| Market Maker | `market_maker.md` | Execution algorithms, order book, inventory management |

### Analysis & Investigation
| Persona | File | Specialization |
|---------|------|----------------|
| Codebase Investigator | `codebase_investigator.md` | Root cause analysis, dependency tracing |
| Code Reviewer | `code_reviewer.md` | Correctness, edge cases, maintainability |
| Research Analyst | `researcher.md` | Literature review, technology evaluation |

### Product & Design
| Persona | File | Specialization |
|---------|------|----------------|
| Product Manager | `product_manager.md` | Requirements, prioritization, roadmapping |
| UX Designer | `ux_designer.md` | Usability, information architecture, accessibility |
| Technical Writer | `technical_writer.md` | API docs, tutorials, architecture decision records |

## Usage

```python
# Security audit with specialized agents
swarm(
    objective="Audit the authentication system for vulnerabilities",
    agents=["architect", "security_expert", "pentester", "threat_modeler"]
)

# Data pipeline review
swarm(
    objective="Review our ETL pipeline for reliability issues",
    agents=["architect", "data_engineer", "sre_engineer"]
)

# Expert panel on technology choice
swarm_adjudicate(
    query="Should we use GraphQL or REST for our public API?",
    panel=["api_designer", "frontend_architect", "performance_engineer"]
)

# Trading system design
swarm(
    objective="Design a market-making strategy for BTC perpetuals",
    agents=["architect", "quant_analyst", "market_maker"]
)
```

## Creating Your Own

1. Create a `.md` file in this directory
2. Follow the format below
3. Restart the server
4. Reference by filename (e.g., `my_expert.md` becomes `my_expert`)

```markdown
# Persona Name

## Role
What this persona does and how it approaches problems.

## Expertise
- Domain area 1
- Domain area 2

## Capabilities
What specific tasks this persona can perform.

## Tools
- analyze
- search
- complete

## Guidelines
1. Behavioral directive 1
2. Behavioral directive 2
```

Set `GEMINI_MCP_PERSONAS_DIR` to load personas from a custom directory.
