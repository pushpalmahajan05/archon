# ARCHON — Agentic Change-Impact Analysis System

> *"Don't guess what will break. Ask ARCHON."*

ARCHON is a multi-agent AI system that performs **evidence-backed architectural change-impact analysis** over software repositories. Given a developer's change request — such as *"Replace Redis with DynamoDB"* — ARCHON reasons from actual code structure, dependency graphs, commit history, architecture decision records, and security context to produce a traceable recommendation with confidence score.

Unlike generic code assistants, ARCHON never invents information. Every claim in its output traces back to a real source: a file, a function, a commit message, a dependency relationship, or a decision record.

---

## Table of Contents

1. [Project Overview & Motivation](#1-project-overview--motivation)
2. [System Architecture](#2-system-architecture)
3. [The Six Agents](#3-the-six-agents)
4. [Knowledge Bases](#4-knowledge-bases)
5. [The Ingestion Pipeline](#5-the-ingestion-pipeline)
6. [The LangGraph Workflow](#6-the-langgraph-workflow)
7. [Technology Stack](#7-technology-stack)
8. [Project Structure](#8-project-structure)
9. [Component Reference](#9-component-reference)
10. [API Reference](#10-api-reference)
11. [Data Models](#11-data-models)
12. [Setup & Installation](#12-setup--installation)
13. [Current Status & Test Results](#13-current-status--test-results)
14. [Design Principles](#14-design-principles)
15. [Known Limitations](#15-known-limitations)
16. [Roadmap](#16-roadmap)

---

## 1. Project Overview & Motivation

### The Problem

Modern software systems are complex. A seemingly simple change — "replace our Redis cache with DynamoDB" — can cascade through dozens of services, break test suites, introduce security vulnerabilities, and contradict architectural decisions made two years ago for good reasons that nobody remembers.

Today, developers face this problem with:
- Manual code search and dependency tracing (time-consuming, error-prone)
- LLM assistants that hallucinate architecture details they don't actually know
- Documentation that is out of date or non-existent

### What ARCHON Does

ARCHON takes a change request and runs it through a **sequential pipeline of six specialised AI agents**, each backed by a real knowledge base. The final output is a structured decision containing:

- A clear recommendation (proceed / don't proceed / proceed with conditions)
- Direct and indirect impacted components, traced through the dependency graph
- Historical rationale: why was the current technology chosen?
- Security implications at the architectural level
- Ranked risks with mitigations
- Concrete evidence for every major claim
- A confidence score that reflects the quality and completeness of available evidence

### Academic Context

ARCHON is a Final Year Project (FYP) system designed to demonstrate that:
1. Multi-agent LLM systems can reason more reliably than single-prompt systems when grounded in structured knowledge
2. Graph databases and vector databases serve complementary roles in architectural analysis (structure vs. semantics)
3. Deterministic parsing should precede LLM reasoning — the LLM reasons *over* evidence, it does not *discover* it

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Developer                         │
│   "Replace Redis with DynamoDB. What breaks?"        │
└──────────────────────────┬──────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│              ARCHON UI  +  FastAPI                   │
│         http://localhost:8000/ui  |  /analyze        │
└──────────────────────────┬──────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│             Orchestrator  (LangGraph)                │
│     Manages ArchonState through the pipeline         │
└──┬───────────────────────────────────────────────┬──┘
   │                                               │
   ▼  Sequential Pipeline                          │
┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  Repository  │→ │Architecture  │→ │ Historian  │ │
│  Agent       │  │  Agent       │  │  Agent     │ │
└──────────────┘  └──────────────┘  └────────────┘ │
                                           │        │
                                           ▼        │
                              ┌─────────────────┐   │
                              │  Impact Agent   │   │
                              └────────┬────────┘   │
                                       ▼            │
                              ┌─────────────────┐   │
                              │ Security Agent  │   │
                              └────────┬────────┘   │
                                       ▼            │
                              ┌─────────────────┐   │
                              │  Synthesizer    │   │
                              │  Agent          │   │
                              └────────┬────────┘   │
                                       │            │
                                       ▼            │
                         ┌─────────────────────┐    │
                         │   ArchonDecision     │    │
                         │   recommendation     │    │
                         │   confidence: 0.87   │    │
                         │   evidence: [...]    │    │
                         └─────────────────────┘    │
                                                     │
   ┌─────────────────────────────────────────────────┘
   │         Both knowledge bases are queried by
   │         every agent throughout the pipeline
   │
   ├──────────────────────┐
   ▼                      ▼
┌────────┐          ┌──────────┐
│ Neo4j  │          │  Qdrant  │
│ Graph  │          │  Vectors │
│   KB   │          │    KB    │
└────────┘          └──────────┘
 Structure           Semantics
 "what connects     "what evidence is
  to what"           relevant"
```

---

## 3. The Six Agents

### Agent 1 — Repository Intelligence Agent

**File:** `app/agents/repository_agent.py`  
**Prompt:** `app/prompts/repository.md`

**Responsibility:** Understand the concrete implementation of the repository. This is the foundation that all other agents build on.

**What it extracts:**
- Important files, modules, packages
- Classes, functions, APIs
- Configuration files (Docker, environment, build)
- External services, databases, caches
- Dependency manifests

**Evidence sources:**
- Source code chunks from Qdrant (semantic search)
- README and documentation from Qdrant
- Repository structure summary from Neo4j

**Output fields:** `components`, `dependencies`, `apis`, `configuration`, `observations`, `evidence`, `confidence`

**Design rule:** Never invent a component. If evidence is insufficient, state *"Insufficient repository evidence."*

---

### Agent 2 — Architecture Reconstruction Agent

**File:** `app/agents/architecture_agent.py`  
**Prompt:** `app/prompts/architecture.md`

**Responsibility:** Reconstruct the current architecture from evidence — not from assumption.

**What it infers:**
- Services, components, layers
- Communication mechanisms (REST, message queue, function call)
- Data stores and their relationships
- External system integrations
- Deployment context (Docker, K8s, etc.)

**Evidence sources:**
- Repository Intelligence findings (from previous agent)
- Architecture graph from Neo4j (services, relationships)
- Docker/config files from Qdrant

**Confidence labels:** `FACT` | `INFERENCE` | `UNKNOWN`

**Output fields:** `architectural_style`, `components`, `component_relationships`, `data_stores`, `external_systems`, `communication_patterns`, `uncertainty`, `evidence`, `confidence`

---

### Agent 3 — Decision Historian Agent

**File:** `app/agents/historian_agent.py`  
**Prompt:** `app/prompts/historian.md`

**Responsibility:** Recover *why* the current architecture exists — the historical rationale behind decisions.

**What it searches:**
- ADRs (Architecture Decision Records) in `/adr`, `/docs/adr`, `/docs/decisions`
- Git commit messages and descriptions
- Pull request descriptions (if available)
- README sections explaining design choices

**Evidence hierarchy:**
1. **CONFIRMED** — explicit ADR or design document
2. **INFERRED** — detailed commit message or PR description
3. **UNKNOWN** — no explicit rationale found

**Why this matters:** Without the Historian, the Synthesizer cannot reason about whether a proposed change contradicts original design intent.

**Output fields:** `decisions[]` each with `decision`, `reason`, `evidence`, `evidence_strength`, `confidence`

---

### Agent 4 — Change Impact Agent

**File:** `app/agents/impact_agent.py`  
**Prompt:** `app/prompts/impact.md`

**Responsibility:** Trace the blast radius of the proposed change through the dependency graph.

**What it traverses:**
- `IMPORTS`, `CALLS`, `DEPENDS_ON`, `USES`, `EXPOSES`, `READS`, `WRITES` relationships in Neo4j
- Up to 4 hops deep by default

**Impact categories:**
- **DIRECT IMPACT** — components that directly use the changed technology
- **INDIRECT IMPACT** — components that depend on directly impacted ones
- **POSSIBLE IMPACT** — may be affected depending on implementation

**Additional analysis:**
- API endpoints affected
- Database/data store changes
- Configuration file changes required
- Tests that need updating
- Deployment/CI pipeline changes

**Output fields:** `change_requested`, `direct_impact[]`, `indirect_impact[]`, `api_impact[]`, `data_impact[]`, `config_impact[]`, `testing_impact[]`, `deployment_impact[]`

---

### Agent 5 — Security Analysis Agent

**File:** `app/agents/security_agent.py`  
**Prompt:** `app/prompts/security.md`

**Responsibility:** Identify **architectural-level** security implications of the proposed change. This is not a vulnerability scanner — it reasons about how the change affects the security posture.

**What it analyses:**
- Trust boundary changes (does a component move from internal to external network?)
- Authentication and authorization implications
- Data flow changes (where does sensitive data now travel?)
- New credentials or secrets required
- Encryption configuration changes
- Service-to-service communication changes

**Risk levels:** `LOW` | `MEDIUM` | `HIGH` | `CRITICAL`

**Key insight:** A change like "Replace Redis (internal) with DynamoDB (external AWS)" fundamentally changes the trust boundary — this agent catches that.

**Output fields:** `security_impact_summary`, `data_flow_changes[]`, `trust_boundary_changes[]`, `access_control[]`, `risks[]` each with `level` and `mitigation`

---

### Agent 6 — Decision Synthesizer Agent

**File:** `app/agents/synthesizer_agent.py`  
**Prompt:** `app/prompts/synthesizer.md`

**Responsibility:** The final reasoning layer. Receives all five agents' findings and produces a single, coherent, evidence-backed recommendation.

**What it does:**
- Weighs all evidence from all agents
- Identifies contradictions between agents and resolves them (or reduces confidence)
- Produces a clear recommendation with reasoning
- Lists realistic alternatives
- Provides a calibrated confidence score

**Final principle:** A strong recommendation is the one best supported by available evidence — not the most confident-sounding one. If evidence is thin, confidence must be low.

**Output fields:** `recommendation`, `reasoning`, `alternatives[]`, `affected_components[]`, `historical_context`, `security_implications[]`, `risks[]`, `evidence[]`, `uncertainties[]`, `confidence`

---

## 4. Knowledge Bases

ARCHON uses two complementary knowledge bases. They are **not interchangeable** — each answers a fundamentally different question.

### Neo4j — The Structure KB

> *"What is connected to what?"*

**Technology:** Neo4j AuraDB (Free tier)  
**Client:** `app/knowledge/neo4j_client.py`

Neo4j stores the structural skeleton of the repository as a property graph.

**Node types:**

| Node | Properties | Description |
|---|---|---|
| `Repository` | `name`, `url` | The root repository node |
| `File` | `path`, `language`, `repository` | Every source file |
| `Function` | `name`, `file`, `lineno`, `repository` | Every parsed function |
| `Class` | `name`, `file`, `repository` | Every parsed class |
| `Module` | `name`, `repository` | Import targets |
| `Dependency` | `name`, `version`, `repository` | Package dependencies |
| `Service` | `name`, `type`, `repository` | Docker/infrastructure services |
| `ADR` | `id`, `title`, `content`, `repository` | Architecture decisions |
| `Commit` | `hash`, `message`, `author`, `date`, `repository` | Git commits |

**Relationship types:**

| Relationship | From → To | Meaning |
|---|---|---|
| `CONTAINS` | Repository → File | Repository owns file |
| `DEFINES` | File → Function/Class | File contains symbol |
| `IMPORTS` | File → Module | Import statement |
| `DEPENDS_ON` | Repository → Dependency | Package dependency |
| `CHANGED_BY` | Repository → Commit | Commit history |
| `DOCUMENTED_BY` | Repository → ADR | Architecture decision |

**Key capability:** The Impact Agent uses multi-hop graph traversal to find all components transitively affected by a change:

```cypher
MATCH path = (n)-[:DEPENDS_ON|CALLS|USES|IMPORTS*1..4]-(target)
WHERE target.name = "Redis" AND n.repository = "my-repo"
RETURN path, n.name AS dependant
```

### Qdrant — The Semantic KB

> *"What evidence is semantically relevant to this query?"*

**Technology:** Qdrant Cloud (Free tier)  
**Client:** `app/knowledge/qdrant_client.py`  
**Embedding model:** `all-MiniLM-L6-v2` (384-dimensional vectors)

Qdrant stores dense vector embeddings of evidence chunks, enabling semantic search — finding relevant code even when the exact words don't match the query.

**Chunk types:**

| Type | Source | Example |
|---|---|---|
| `code` | Source files (400-line chunks with 50-line overlap) | A function body |
| `readme` | README.md | Project description |
| `documentation` | Other `.md` files | Architecture docs |
| `commit` | Git commit messages | "Fix Redis connection pooling" |
| `adr` | Architecture Decision Records | "ADR-003: Use Redis for sessions" |

**Payload schema per chunk:**
```json
{
  "text": "...",
  "repository": "flask",
  "file": "src/flask/templating.py",
  "type": "code",
  "language": "python",
  "line_start": 43,
  "line_end": 72
}
```

**Indexed payload fields:** `repository`, `type`, `file` (required for filtered search)

---

## 5. The Ingestion Pipeline

**Entry point:** `app/ingestion/indexer.py`

The ingestion pipeline converts a raw repository into structured knowledge. It runs deterministically — no LLM involvement at this stage.

```
Repository directory
        │
        ├─► repository_loader.py  ── scan files, detect languages, skip binaries
        │
        ├─► code_parser.py        ── AST parsing (Python), regex (JS/TS/Java)
        │                             extracts: classes, functions, imports
        │                             produces: code chunks for Qdrant
        │
        ├─► dependency_parser.py  ── reads: requirements.txt, package.json,
        │                             pom.xml, go.mod, docker-compose.yml
        │
        ├─► git_parser.py         ── last 200 commits: hash, author, date, message
        │
        ├─► adr_parser.py         ── searches: /adr, /docs/adr, /docs/decisions
        │                             for *.md files matching ADR naming patterns
        │
        ▼
  ┌────────────┐        ┌──────────┐
  │   Neo4j    │        │  Qdrant  │
  │  (MERGE)   │        │  (upsert)│
  └────────────┘        └──────────┘
```

### Incremental Indexing

A manifest file (`data/repositories/<name>/.archon_manifest.json`) tracks:
- SHA-256 hash of every indexed file
- Last indexed commit hash
- IDs of indexed ADRs

On re-ingestion:
- Only files whose content hash changed are re-parsed
- Old Qdrant vectors for changed files are deleted before new ones are uploaded
- Only commits newer than `last_commit` are added to Neo4j
- Deleted files are removed from the graph via `DETACH DELETE`

This makes re-ingestion after a `git pull` very fast — typically only a handful of files are re-processed.

---

## 6. The LangGraph Workflow

**Entry point:** `app/orchestrator/graph.py`

ARCHON uses LangGraph's `StateGraph` to manage state flow through the agent pipeline. All agents read from and write to a shared `ArchonState` TypedDict.

### Pipeline

```
START
  │
  ▼
[repository_agent]    → populates state["repository_findings"]
  │
  ▼
[architecture_agent]  → reads repository_findings
                      → populates state["architecture_findings"]
  │
  ▼
[historian_agent]     → populates state["history_findings"]
  │
  ▼
[impact_agent]        → reads repository_findings + architecture_findings
                      → populates state["impact_findings"]
  │
  ▼
[security_agent]      → reads architecture_findings + impact_findings
                      → populates state["security_findings"]
  │
  ▼
[synthesizer_agent]   → reads ALL five findings
                      → populates state["final_decision"]
  │
  ▼
END
```

### ArchonState

```python
class ArchonState(TypedDict, total=False):
    repository_path: str
    repository_name: str
    user_query: str
    plan: List[str]
    repository_findings: Dict[str, Any]
    architecture_findings: Dict[str, Any]
    history_findings: Dict[str, Any]
    impact_findings: Dict[str, Any]
    security_findings: Dict[str, Any]
    final_decision: Dict[str, Any]
    evidence: List[Dict[str, Any]]
    errors: List[str]
    session_id: str
    started_at: str
```

Each agent is a pure function `(ArchonState) → ArchonState`. Errors are appended to `state["errors"]` but never abort the pipeline — partial results are always returned.

---

## 7. Technology Stack

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| Language | Python | 3.13 | Core runtime |
| API Framework | FastAPI | 0.111 | REST API + UI serving |
| ASGI Server | Uvicorn | 0.29 | Production-grade async server |
| Agent Orchestration | LangGraph | 1.2 | Stateful agent pipeline |
| LLM | Groq API | — | `openai/gpt-oss-20b` or `120b` |
| Embeddings | sentence-transformers | 2.7 | `all-MiniLM-L6-v2` (384-dim) |
| Graph Database | Neo4j AuraDB | 6.4 driver | Structural knowledge |
| Vector Database | Qdrant Cloud | 1.19 client | Semantic evidence |
| Git Parsing | GitPython | 3.2 | Commit history extraction |
| Data Validation | Pydantic | 2.7 | All models and API schemas |
| Settings | pydantic-settings | 2.2 | `.env` loading |
| Testing | pytest | 9.1 | 15 unit + integration tests |
| Frontend | Vanilla HTML/CSS/JS | — | Single-file UI, no build step |

---

## 8. Project Structure

```
ARCHON1/
│
├── .env                          ← Your credentials (never commit)
├── .env.example                  ← Template for setting up .env
├── .gitignore
├── requirements.txt
├── README.md                     ← This file
├── USER_GUIDE.md                 ← Step-by-step usage guide
├── QUICKSTART.md                 ← Quick reference card
│
├── app/
│   ├── __init__.py
│   ├── main.py                   ← FastAPI app (5 endpoints + UI serving)
│   ├── config.py                 ← Settings loaded from .env
│   │
│   ├── models/
│   │   ├── state.py              ← ArchonState TypedDict (shared pipeline state)
│   │   ├── evidence.py           ← Evidence, EvidencedClaim models
│   │   └── decision.py           ← ArchonDecision (final output model)
│   │
│   ├── llm/
│   │   ├── groq_client.py        ← Groq API client; mock mode when no key
│   │   └── embeddings.py         ← sentence-transformers; fallback to zero-vector
│   │
│   ├── knowledge/
│   │   ├── neo4j_client.py       ← Neo4j driver wrapper; all MERGE operations
│   │   ├── qdrant_client.py      ← Qdrant wrapper; upsert, search, delete
│   │   ├── graph_queries.py      ← High-level Neo4j queries for agents
│   │   └── vector_search.py      ← High-level Qdrant search helpers
│   │
│   ├── ingestion/
│   │   ├── repository_loader.py  ← Clone/scan repos; language detection
│   │   ├── code_parser.py        ← AST (Python) + regex (JS/Java) parser
│   │   ├── dependency_parser.py  ← requirements.txt, package.json, go.mod etc.
│   │   ├── git_parser.py         ← Last 200 commits via GitPython
│   │   ├── adr_parser.py         ← ADR discovery and parsing
│   │   └── indexer.py            ← Incremental ingestion orchestrator
│   │
│   ├── agents/
│   │   ├── _base.py              ← load_prompt(), safe_json_parse()
│   │   ├── repository_agent.py
│   │   ├── architecture_agent.py
│   │   ├── historian_agent.py
│   │   ├── impact_agent.py
│   │   ├── security_agent.py
│   │   └── synthesizer_agent.py
│   │
│   ├── prompts/
│   │   ├── orchestrator.md       ← Orchestrator meta-prompt
│   │   ├── repository.md         ← Repository agent instructions
│   │   ├── architecture.md       ← Architecture agent instructions
│   │   ├── historian.md          ← Historian agent instructions
│   │   ├── impact.md             ← Impact agent instructions
│   │   ├── security.md           ← Security agent instructions
│   │   └── synthesizer.md        ← Synthesizer agent instructions
│   │
│   └── orchestrator/
│       ├── graph.py              ← LangGraph StateGraph construction
│       └── orchestrator.py       ← run_analysis() entry point
│
├── scripts/
│   ├── test_connections.py       ← Verify Groq, Neo4j, Qdrant, Embeddings
│   ├── ingest_repo.py            ← CLI ingestion tool
│   ├── build_graph.py            ← Re-index only Neo4j
│   ├── build_vectors.py          ← Re-index only Qdrant
│   └── test_archon.py            ← End-to-end CLI analysis runner
│
├── tests/
│   ├── conftest.py               ← Fixtures; all services mocked for offline tests
│   ├── test_repository.py
│   ├── test_architecture.py
│   ├── test_history.py
│   ├── test_impact.py
│   ├── test_security.py
│   └── test_synthesis.py         ← Includes full pipeline smoke test
│
├── frontend/
│   └── index.html                ← Complete web UI (no build step needed)
│
├── data/
│   └── repositories/             ← Cloned repositories stored here
│       └── <name>/
│           └── .archon_manifest.json  ← Incremental indexing state
│
└── Reference/
    ├── architecture-flow-diagram.excalidraw
    ├── archon_plan_text.txt
    └── Build ARCHON Project Plan.pdf
```

---

## 9. Component Reference

### `app/llm/groq_client.py`

Two functions:
- `ask_groq(system, user) → str` — plain text response
- `ask_groq_json(system, user) → dict` — parses JSON from response, strips markdown fences

Both automatically return mock responses when `GROQ_API_KEY` starts with `PLACEHOLDER`, enabling offline testing.

### `app/llm/embeddings.py`

- `embed_text(text) → List[float]` — single text to 384-dim vector
- `embed_texts(texts) → List[List[float]]` — batched
- Lazy-loads `all-MiniLM-L6-v2` on first call
- Falls back to a deterministic hash-based zero vector if `sentence-transformers` is not installed

### `app/knowledge/neo4j_client.py`

All write operations use `MERGE` — safe to call repeatedly without creating duplicates.

Key methods:
- `create_repository()`, `create_file()`, `create_function()`, `create_class()`
- `create_import()`, `create_dependency()`, `create_service()`
- `create_adr()`, `create_commit()`
- `find_dependencies_of(component, repo, depth)` — impact graph traversal
- `get_repository_summary(repo)` — node counts by type
- `run(cypher, params)` — raw query; returns serialized dicts (Neo4j `Node` objects are automatically converted)

### `app/knowledge/qdrant_client.py`

- `upsert(chunks)` — embed and upload; auto-creates collection and payload indexes
- `search(query, repository, evidence_type, top_k)` — semantic search with optional filters
- `delete_by_repository(repo)` — wipe all chunks for a repository
- `delete_by_file(repo, file_path)` — wipe chunks for a single file (used by incremental indexer)
- `count(repository)` — count vectors

Uses `query_points` API (qdrant-client v1.7+).

### `app/ingestion/indexer.py`

Main function: `ingest_repository(repo_path, repo_name, progress_callback, force_full)`

- On first run or `force_full=True`: full ingestion
- On subsequent runs: loads manifest, diffs file hashes, only re-processes changed files
- Saves updated manifest on completion

### `app/orchestrator/orchestrator.py`

Main function: `run_analysis(repository_name, user_query, repository_path) → ArchonDecision`

- Builds initial `ArchonState`
- Invokes the LangGraph pipeline
- Converts `state["final_decision"]` into a typed `ArchonDecision` Pydantic model
- Returns partial results even if some agents failed

### `app/agents/_base.py`

- `load_prompt(name)` — reads `app/prompts/<name>.md`; returns fallback string if missing
- `safe_json_parse(text, fallback)` — strips markdown fences, extracts first `{...}` block, returns fallback on failure

---

## 10. API Reference

All endpoints are documented interactively at **http://localhost:8000/docs**

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | API status and current model |
| `GET` | `/repositories` | List all ingested repository names |
| `POST` | `/analyze` | Run full 6-agent analysis |
| `POST` | `/ingest` | Ingest repository (background task) |
| `GET` | `/ingest/{name}/status` | Poll ingestion progress |
| `GET` | `/` | Root — redirects to UI or returns API info |
| `GET` | `/ui` | Serves the frontend web UI |
| `GET` | `/docs` | Interactive Swagger API docs |

### POST /analyze

**Request:**
```json
{
  "repository": "flask",
  "query": "Replace Jinja2 with Mako. What are the impacts?"
}
```

**Response:**
```json
{
  "query": "...",
  "repository": "flask",
  "recommendation": "Do not replace Jinja2...",
  "reasoning": "...",
  "alternatives": ["Keep Jinja2", "Use Mako with explicit escaping"],
  "affected_components": ["templating module", "render_template API"],
  "direct_impact": ["templating"],
  "indirect_impact": ["tests", "app context"],
  "historical_context": "Flask chose Jinja2 for auto-escaping...",
  "security_implications": ["Mako lacks auto-escaping by default..."],
  "risks": [{"description": "...", "level": "HIGH", "mitigation": "..."}],
  "evidence": [{"source": "...", "type": "code", "content": "..."}],
  "uncertainties": ["..."],
  "confidence": 0.60,
  "agent_findings": { "repository": {...}, "architecture": {...}, ... },
  "session_id": "f5d3d78e",
  "processing_time_seconds": 85.79
}
```

---

## 11. Data Models

### ArchonDecision (`app/models/decision.py`)

The final output of `run_analysis()`. All fields are typed Pydantic models.

### Evidence (`app/models/evidence.py`)

```python
class Evidence(BaseModel):
    source: str           # file path, commit hash, ADR id
    evidence_type: EvidenceType  # code | adr | commit | readme | graph | semantic
    content: str          # actual text snippet
    repository: str
    file_path: str
    line_start: int
    line_end: int
    confidence: float
```

### ArchonState (`app/models/state.py`)

TypedDict shared across the entire LangGraph pipeline. Every agent reads the existing state and returns an updated copy.

---

## 12. Setup & Installation

```powershell
# 1. Navigate to project
cd "c:\Users\Pushpal Mahajan\Documents\Sem 7\FYP\ARCHON1"

# 2. Create and activate virtual environment
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure credentials
# Edit .env — add GROQ_API_KEY, NEO4J_*, QDRANT_*

# 5. Verify connections
.\.venv\Scripts\python.exe scripts/test_connections.py

# 6. Ingest a repository
.\.venv\Scripts\python.exe scripts/ingest_repo.py https://github.com/pallets/flask.git

# 7. Run analysis
.\.venv\Scripts\python.exe scripts/test_archon.py --repo flask --query "Replace Jinja2 with Mako"

# 8. Start the web server
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

For full setup and usage details, see **[USER_GUIDE.md](USER_GUIDE.md)**.

---

## 13. Current Status & Test Results

### Test Suite

```
platform win32 -- Python 3.13.14 -- pytest 9.1.1

tests/test_architecture.py  ✓  2/2
tests/test_history.py       ✓  2/2
tests/test_impact.py        ✓  3/3
tests/test_repository.py    ✓  3/3
tests/test_security.py      ✓  2/2
tests/test_synthesis.py     ✓  3/3  (includes full pipeline smoke test)

15 passed in 0.76s
```

Tests use fully mocked services (Neo4j, Qdrant, Groq) via `conftest.py` autouse fixtures — run offline, no API calls.

### Live Analysis Results

Verified end-to-end on **Flask** (`pallets/flask`):

| Metric | Value |
|---|---|
| Repository | pallets/flask |
| Files indexed | 230 |
| Functions parsed | 1,462 |
| Classes parsed | 160 |
| Vectors in Qdrant | 468 |
| Commits in Neo4j | 200 |
| Analysis query | Replace Jinja2 with Mako |
| Processing time | 85.79 seconds |
| Confidence score | 0.60 |
| All 6 agents ran | ✅ |

### Service Connectivity

```
✓  Groq LLM (openai/gpt-oss-20b)
✓  Neo4j AuraDB
✓  Qdrant Cloud
✓  Embeddings (all-MiniLM-L6-v2)
```

---

## 14. Design Principles

**1. Evidence first, reasoning second.**  
Deterministic parsers (AST, regex, git log) run before any LLM call. The LLM reasons *over* structured evidence — it does not discover architecture by hallucination.

**2. Structured knowledge over raw text.**  
Neo4j stores relationships that enable graph traversal (impact chains). Qdrant stores semantic evidence for retrieval. Neither replaces the other.

**3. Confidence must reflect evidence quality.**  
The system actively reduces confidence when evidence is thin, contradictory, or absent. A result with 0.3 confidence and explicit uncertainties is more honest and useful than a confident hallucination.

**4. Errors are not failures.**  
Any agent can fail (network error, JSON parse failure, empty evidence) without aborting the pipeline. Partial results are always returned. Errors are logged in `state["errors"]`.

**5. Agents specialise.**  
The Repository Agent does not make architectural recommendations. The Historian Agent does not trace code dependencies. The Security Agent does not reconstruct architecture. Specialisation improves output quality and makes the system easier to debug.

**6. Prompts are files, not strings.**  
Agent instructions live in `app/prompts/*.md` — editable without touching Python code. This makes prompt engineering accessible and the system customisable without a code deployment.

---

## 15. Known Limitations

| Limitation | Detail |
|---|---|
| No ADRs in most repos | Without ADRs, the Historian falls back to commit inference (confidence: 0.2–0.4). Repos with explicit ADRs get much better historical analysis. |
| Graph completeness | Neo4j only has relationships derived from import statements and explicit dependencies — dynamic relationships (e.g. runtime service discovery) are not captured. |
| No code execution | ARCHON reads code but does not run it. Dynamic behaviours and runtime-only dependencies are invisible to it. |
| Sequential pipeline | Agents run one after another. Parallelising Repository + Historian + Architecture would reduce latency by ~40%. Not implemented yet. |
| LLM context limits | Very large repositories with dense evidence can exceed Groq's context window. Evidence is truncated at ~3,000 characters per agent prompt. |
| English-only prompts | Agent prompts are in English. Non-English commit messages and documentation will still be ingested but reasoning quality may be lower. |

---

## 16. Roadmap

### Short term
- [ ] Parallel agent execution (Repository, Historian, Architecture can run concurrently)
- [ ] PR/Issue ingestion from GitHub API (richer Historian evidence)
- [ ] Confidence calibration — benchmark against known architectural changes

### Medium term
- [ ] Multi-repository analysis (compare architectures across repos)
- [ ] ADR auto-generation from analysis results
- [ ] Re-analysis with follow-up questions (conversational mode)

### Long term
- [ ] Docker deployment (Dockerfile + docker-compose)
- [ ] Evaluation harness for academic benchmarking
- [ ] Support for more languages (Rust, Ruby, C#)

---

*ARCHON — Agentic Change-Impact Analysis System*  
*FYP Project | Python 3.13 | Windows | Neo4j + Qdrant + Groq*
