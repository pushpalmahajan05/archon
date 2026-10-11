# ARCHON Quickstart Guide

## ✅ What's Done

Your complete ARCHON system is now built and testable! Here's what you have:

### 🏗 Architecture
- **6 Specialized Agents** working in a sequential LangGraph pipeline
- **Neo4j** integration for structural knowledge (graph database)
- **Qdrant** integration for semantic knowledge (vector database)
- **Groq LLM** integration for reasoning
- **FastAPI** backend with REST API
- **Web UI** (single-page HTML app — no build needed)
- Full **ingestion pipeline** for repositories

### 📁 Project Structure
```
ARCHON1/
├── app/
│   ├── agents/              # 6 specialized agents
│   ├── knowledge/           # Neo4j + Qdrant clients
│   ├── llm/                 # Groq client + embeddings
│   ├── ingestion/           # Repository scanning & parsing
│   ├── orchestrator/        # LangGraph pipeline
│   ├── prompts/             # Agent instructions (.md files)
│   ├── models/              # Pydantic models
│   ├── main.py              # FastAPI app
│   └── config.py            # Settings
├── scripts/                 # CLI utilities
├── tests/                   # 15 passing tests
├── frontend/                # Web UI (index.html)
├── .env                     # Your configuration (edit this!)
└── requirements.txt         # Python dependencies
```

---

## 🚀 How to Use

### 1. Configure Your API Keys

Edit `.env` and add your credentials:

```env
# Get from https://console.groq.com
GROQ_API_KEY=your_groq_key_here

# Get from https://neo4j.com/cloud/aura/
NEO4J_URI=neo4j+s://xxxxxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password_here

# Get from https://qdrant.cloud/
QDRANT_URL=https://xxxxxxxx.cloud.qdrant.io
QDRANT_API_KEY=your_key_here
```

**Important:** The system works in "placeholder mode" without these keys (returns mock results), but real analysis requires:
- ✅ **Groq API key** (for LLM reasoning) — **most important**
- ✅ **Neo4j** (for dependency graphs)
- ✅ **Qdrant** (for semantic search)

### 2. Test the Connections

```powershell
.\.venv\Scripts\python.exe scripts/test_connections.py
```

You should see:
```
✓  Groq
✓  Neo4j  
✓  Qdrant
✓  Embeddings
```

### 3. Ingest a Repository

Pick a small test repository first:

```powershell
# Option 1: From a git URL
.\.venv\Scripts\python.exe scripts/ingest_repo.py https://github.com/redis/redis-py.git

# Option 2: From a local path
.\.venv\Scripts\python.exe scripts/ingest_repo.py --local C:\path\to\repo

# Option 3: Custom name
.\.venv\Scripts\python.exe scripts/ingest_repo.py https://github.com/user/repo.git --name my-repo
```

This will:
- Clone the repository (if URL)
- Parse all code files, dependencies, commits, ADRs
- Build the Neo4j graph (structure)
- Build the Qdrant vectors (semantic evidence)

### 4. Run ARCHON Analysis

```powershell
.\.venv\Scripts\python.exe scripts/test_archon.py --repo redis-py --query "Replace Redis with DynamoDB. What are the impacts?"
```

ARCHON will run all 6 agents:
1. **Repository Agent** → understand files, classes, functions
2. **Architecture Agent** → reconstruct services & components
3. **Historian Agent** → find ADRs and historical rationale
4. **Impact Agent** → trace direct and indirect impacts
5. **Security Agent** → analyze security implications
6. **Synthesizer Agent** → produce final recommendation

Output example:
```
═══════════════════════════════════════════════════════════
  RECOMMENDATION
═══════════════════════════════════════════════════════════
  Migration is feasible but requires careful planning...

  REASONING
  Redis is deeply integrated into the caching layer...

  DIRECT IMPACT
    • CacheService
    • OrderService
    • deployment/config.yaml

  INDIRECT IMPACT
    • CheckoutAPI
    • UserService tests
    • monitoring dashboards

  SECURITY IMPLICATIONS
    • IAM role changes required
    • Data encryption at rest configuration
    • Network security group updates

  RISKS
    [MEDIUM] Session data migration complexity
    [HIGH] Downtime during cutover
    [LOW] Cost increase with DynamoDB

  CONFIDENCE: 0.87
═══════════════════════════════════════════════════════════
```

---

## 🌐 Web UI

### Start the API Server

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Open the UI

Navigate to: **http://localhost:8000/**

You'll see the ARCHON web interface where you can:
- Browse ingested repositories
- Submit change requests
- View analysis results with confidence scores
- See evidence trails
- Ingest new repositories directly from the UI

---

## 📦 API Endpoints

Once the server is running:

### `GET /health`
Health check and API status.

### `GET /repositories`
List all ingested repositories.

### `POST /analyze`
Run a full ARCHON analysis.

**Request:**
```json
{
  "repository": "my-repo",
  "query": "Replace PostgreSQL with MySQL. What are the impacts?"
}
```

**Response:**
```json
{
  "recommendation": "...",
  "reasoning": "...",
  "confidence": 0.85,
  "direct_impact": [...],
  "indirect_impact": [...],
  "security_implications": [...],
  "risks": [...],
  "evidence": [...],
  "processing_time_seconds": 12.3
}
```

### `POST /ingest`
Ingest a new repository (runs in background).

**Request:**
```json
{
  "url": "https://github.com/user/repo.git",
  "name": "my-repo"
}
```

### `GET /ingest/{name}/status`
Check ingestion status.

### Interactive API docs:
- Swagger: **http://localhost:8000/docs**
- ReDoc: **http://localhost:8000/redoc**

---

## 🧪 Tests

Run the full test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

All 15 tests should pass:
```
✓ test_repository_agent_runs
✓ test_architecture_agent_runs
✓ test_historian_agent_runs
✓ test_impact_agent_runs
✓ test_security_agent_runs
✓ test_synthesizer_agent_runs
✓ test_full_pipeline_smoke
... (15/15 passed)
```

---

## 📚 Example Queries

### Good Questions for ARCHON:

1. **Technology Replacement**
   - "Replace Redis with DynamoDB. What are the impacts?"
   - "Migrate from PostgreSQL to MySQL"
   - "Switch from REST to GraphQL"

2. **Dependency Changes**
   - "Upgrade React from v16 to v18"
   - "Remove the Express dependency"
   - "What depends on the UserService?"

3. **Architecture Changes**
   - "Split the monolith into microservices"
   - "Move authentication to a separate service"
   - "What would break if we remove the caching layer?"

4. **Security Changes**
   - "Add OAuth2 authentication"
   - "Encrypt all database connections"
   - "Move secrets from config files to a vault"

---

## 🛠 Troubleshooting

### "Placeholder mode" responses
→ Add your `GROQ_API_KEY` to `.env` and restart

### "Neo4j not connected"
→ Check `NEO4J_URI`, `NEO4J_PASSWORD` in `.env`

### "No repositories ingested"
→ Run `scripts/ingest_repo.py` first

### Import errors
→ Make sure you're using the venv:
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### API won't start
→ Check port 8000 is not already in use:
```powershell
netstat -ano | findstr :8000
```

---

## 📈 Next Steps

### For Development:
1. Add more test repositories to `data/repositories/`
2. Customize agent prompts in `app/prompts/`
3. Add new agent nodes to the LangGraph pipeline
4. Extend the Neo4j schema in `knowledge/neo4j_client.py`

### For Evaluation:
1. Measure accuracy on known architectural changes
2. Compare confidence scores against ground truth
3. Evaluate evidence quality and traceability
4. Test on repositories of different sizes and languages

### For Production:
1. Add authentication/authorization
2. Set up persistent job queue for ingestion
3. Add caching layer for repeated queries
4. Deploy with Docker/K8s

---

## 🎯 Demo Scenario

Try this complete flow:

```powershell
# 1. Test connections
.\.venv\Scripts\python.exe scripts/test_connections.py

# 2. Ingest a demo repo
.\.venv\Scripts\python.exe scripts/ingest_repo.py https://github.com/redis/redis-py.git

# 3. Run analysis
.\.venv\Scripts\python.exe scripts/test_archon.py

# 4. Start the web UI
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload

# 5. Open browser → http://localhost:8000
```

---

## 📄 Documentation

- **Architecture Design**: `Reference/architecture-flow-diagram.excalidraw`
- **Project Plan**: `Reference/Build ARCHON Project Plan.pdf`
- **Agent Prompts**: `app/prompts/*.md`
- **API Docs**: http://localhost:8000/docs (when server is running)

---

## ✨ Key Features

- ✅ **Evidence-Based**: Every recommendation traces to source files, commits, ADRs
- ✅ **Multi-Agent**: 6 specialized agents with clear responsibilities
- ✅ **Testable**: Full test coverage with placeholder mode for CI/CD
- ✅ **Production-Ready**: FastAPI backend, proper error handling, structured outputs
- ✅ **Extensible**: Easy to add new agents or customize prompts

---

**ARCHON is ready to analyze architectural changes!** 🚀

Need help? Check the logs in the console or open an issue on GitHub.
