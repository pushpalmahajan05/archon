# ARCHON User Guide

> **ARCHON** — Agentic Change-Impact Analysis System  
> A multi-agent AI that reasons over real repository evidence to answer: *"What happens if I make this architectural change?"*

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [First-Time Setup](#2-first-time-setup)
3. [Configuring Your API Keys](#3-configuring-your-api-keys)
4. [Verifying All Connections](#4-verifying-all-connections)
5. [Ingesting a Repository](#5-ingesting-a-repository)
6. [Running an Analysis](#6-running-an-analysis)
7. [Using the Web UI](#7-using-the-web-ui)
8. [Using the REST API](#8-using-the-rest-api)
9. [Incremental Updates](#9-incremental-updates)
10. [Understanding the Output](#10-understanding-the-output)
11. [Writing Good Queries](#11-writing-good-queries)
12. [User Tweaks & Customisation](#12-user-tweaks--customisation)
13. [Troubleshooting](#13-troubleshooting)
14. [Frequently Asked Questions](#14-frequently-asked-questions)

---

## 1. Prerequisites

| Requirement | Notes |
|---|---|
| Windows 10/11 | Native Windows, no WSL needed |
| Python 3.11+ | Installed via [python.org](https://www.python.org/downloads/) |
| Git | [git-scm.com](https://git-scm.com/) — needed for cloning repos |
| Groq API key | Free at [console.groq.com](https://console.groq.com) |
| Neo4j AuraDB (Free) | Free at [console.neo4j.io](https://console.neo4j.io) |
| Qdrant Cloud (Free) | Free at [cloud.qdrant.io](https://cloud.qdrant.io) |

> **Note:** The system works without Neo4j and Qdrant keys in placeholder/mock mode, but real analysis requires all three services.

---

## 2. First-Time Setup

Open PowerShell and run these commands once:

```powershell
# Navigate to the project folder
cd "c:\Users\Pushpal Mahajan\Documents\Sem 7\FYP\ARCHON1"

# Create the Python virtual environment
py -m venv .venv

# Activate it
.\.venv\Scripts\Activate.ps1

# Install all dependencies
pip install -r requirements.txt
```

> After this, always activate the venv before using ARCHON:
> ```powershell
> .\.venv\Scripts\Activate.ps1
> ```

---

## 3. Configuring Your API Keys

Edit the `.env` file in the project root. Fill in your real credentials:

```env
# ── Groq (LLM reasoning) ─────────────────────────────────────────
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=openai/gpt-oss-20b          # recommended model

# ── Neo4j AuraDB (structural graph) ──────────────────────────────
NEO4J_URI=neo4j+s://abcd1234.databases.neo4j.io
NEO4J_USERNAME=abcd1234                # same as your instance ID
NEO4J_PASSWORD=your_password_here
NEO4J_DATABASE=abcd1234               # same as your instance ID

# ── Qdrant Cloud (semantic vectors) ──────────────────────────────
QDRANT_URL=https://your-cluster-id.us-east-2-0.aws.cloud.qdrant.io
QDRANT_API_KEY=your_qdrant_key_here
QDRANT_COLLECTION=archon              # name of collection to use
```

### Where to find each key

**Groq:**
1. Go to [console.groq.com](https://console.groq.com)
2. Click **API Keys** → **Create API Key**
3. Copy the key starting with `gsk_`

**Neo4j AuraDB:**
1. Go to [console.neo4j.io](https://console.neo4j.io)
2. Create a **Free AuraDB** instance
3. The URI is shown as `neo4j+s://xxxxxxxx.databases.neo4j.io`
4. **Important:** Both `NEO4J_USERNAME` and `NEO4J_DATABASE` must be set to the instance ID (the `xxxxxxxx` part), **not** `neo4j`
5. The password is shown once at creation — save it. To reset: instance menu → **Reset Password**

**Qdrant Cloud:**
1. Go to [cloud.qdrant.io](https://cloud.qdrant.io)
2. Create a **Free Cluster**
3. Under **Cluster Details**, copy the URL and API key

### Available Groq models

| Model | Speed | Quality | Recommended for |
|---|---|---|---|
| `openai/gpt-oss-20b` | Fast | Good | Default — best balance |
| `openai/gpt-oss-120b` | Slower | Best | Complex repositories |

Change the model by editing `GROQ_MODEL` in `.env`.

---

## 4. Verifying All Connections

Before ingesting anything, confirm all services are reachable:

```powershell
.\.venv\Scripts\python.exe scripts/test_connections.py
```

Expected output:
```
====================================================
  ARCHON Connection Tests
====================================================
── Groq LLM ─────────────────────────────────────
  ✓  Response: ARCHON connection successful
── Neo4j ────────────────────────────────────────
  ✓  Neo4j connected and verified.
── Qdrant ───────────────────────────────────────
  ✓  Qdrant connected. Collection has 0 vectors.
── Embeddings ───────────────────────────────────
  ✓  Embeddings OK. Vector dim=384
── Summary ──────────────────────────────────────
  ✓  All critical services ready.
====================================================
```

If any service fails, see [Troubleshooting](#13-troubleshooting).

---

## 5. Ingesting a Repository

Ingestion parses the repository and builds the two knowledge bases. **You must do this before analysis.**

### From a remote URL

```powershell
# Clones the repository and ingests it
.\.venv\Scripts\python.exe scripts/ingest_repo.py https://github.com/pallets/flask.git

# With a custom name
.\.venv\Scripts\python.exe scripts/ingest_repo.py https://github.com/pallets/flask.git --name flask
```

### From a local folder you already have

```powershell
.\.venv\Scripts\python.exe scripts/ingest_repo.py --local C:\path\to\your\project
.\.venv\Scripts\python.exe scripts/ingest_repo.py --local C:\path\to\project --name my-project
```

### What ingestion does

```
Repository folder
      │
      ├─ Scans all source files (Python, JS, TS, Java, Go, etc.)
      ├─ Parses classes, functions, imports (deterministic AST)
      ├─ Extracts dependencies (requirements.txt, package.json, pom.xml, go.mod)
      ├─ Reads git commit history (last 200 commits)
      ├─ Finds ADRs (in /adr, /docs/adr, /docs/decisions)
      │
      ├─► Neo4j  ── nodes: Repository, File, Function, Class, Module,
      │            ──       Dependency, Service, ADR, Commit
      │            ── edges: CONTAINS, DEFINES, IMPORTS, DEPENDS_ON,
      │                      CHANGED_BY, DOCUMENTED_BY
      │
      └─► Qdrant ── 384-dim vectors (all-MiniLM-L6-v2)
                   ── chunk types: code, readme, documentation, commit, adr
```

### Progress output

```
  [████████████████████] 100%  Ingestion complete

  ── Ingestion Summary ─────────────────────────────
    repository        : flask
    files             : 230
    functions         : 1462
    classes           : 160
    imports           : 675
    dependencies      : 104
    commits_new       : 200
    adrs              : 0
    vectors_added     : 468
```

### Ingestion is incremental

If you run ingest on the same repository again, it only processes what changed:

```
Files: 3 changed/new, 227 unchanged, 0 deleted
New commits: 2
Vectors added: 14   ← only the changed files, not all 468
```

A manifest file (`data/repositories/<name>/.archon_manifest.json`) tracks SHA-256 hashes of every file and the last indexed commit hash.

### Force a full re-index

```powershell
.\.venv\Scripts\python.exe scripts/ingest_repo.py --local data\repositories\flask --name flask --force
```

### List all ingested repositories

```powershell
.\.venv\Scripts\python.exe scripts/test_connections.py
# or via API:
Invoke-WebRequest -Uri http://localhost:8000/repositories -UseBasicParsing | Select-Object -ExpandProperty Content
```

---

## 6. Running an Analysis

### Option A — CLI (quickest)

```powershell
.\.venv\Scripts\python.exe scripts/test_archon.py --repo flask --query "Replace Jinja2 with Mako. What are the impacts?"
```

With a URL (ingests first, then analyses):
```powershell
.\.venv\Scripts\python.exe scripts/test_archon.py --url https://github.com/pallets/flask.git --ingest --query "Remove the Werkzeug dependency"
```

### Option B — Web UI

```powershell
# Start the server
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open **http://localhost:8000/ui** in your browser.

1. Select the repository from the dropdown (or type its name)
2. Type your change request in the text box
3. Click **Analyze**
4. Results appear as cards: Recommendation, Impact, Risks, Security, History, Evidence

### Option C — Direct Python

```python
from app.orchestrator.orchestrator import run_analysis

decision = run_analysis(
    repository_name="flask",
    user_query="Replace Jinja2 with Mako"
)

print(decision.recommendation)
print(f"Confidence: {decision.confidence}")
```

---

## 7. Using the Web UI

Start the server first, then go to **http://localhost:8000/ui**.

### UI Sections

**Left Panel — Analysis**
- Select or type a repository name
- Enter your change request
- Click **Analyze** (takes 30–90 seconds with live API)

**Left Panel — Ingest Repository**
- Paste a Git URL to clone and ingest a new repository
- The progress updates every 3 seconds
- Repository appears in the dropdown once done

**Left Panel — Repositories**
- Lists all already-ingested repositories
- Click any to auto-fill the name field

**Right Panel — Results**
Cards appear for:
- ✅ **Recommendation** — the final answer with confidence bar
- 💥 **Impact** — direct and indirect affected components
- ⚠ **Risks** — ranked LOW / MEDIUM / HIGH / CRITICAL with mitigations
- 🔒 **Security Implications** — architectural security consequences
- 📜 **Historical Context** — why decisions were made
- 🔀 **Alternatives** — other options considered
- 📋 **Evidence** — traceable sources (files, commits, ADRs)
- ❓ **Uncertainties** — what ARCHON couldn't determine

### API Documentation UI

Go to **http://localhost:8000/docs** for the interactive Swagger UI where you can test all endpoints directly in the browser.

---

## 8. Using the REST API

### Health check

```powershell
Invoke-WebRequest -Uri http://localhost:8000/health -UseBasicParsing
# → {"status":"ok","model":"openai/gpt-oss-20b"}
```

### List repositories

```powershell
Invoke-WebRequest -Uri http://localhost:8000/repositories -UseBasicParsing
# → {"repositories":["flask","redis-py"]}
```

### Run an analysis

```powershell
$body = '{"repository":"flask","query":"Replace Jinja2 with Mako"}'
Invoke-WebRequest -Uri http://localhost:8000/analyze `
  -Method POST `
  -ContentType "application/json" `
  -Body $body `
  -UseBasicParsing | Select-Object -ExpandProperty Content
```

### Ingest a repository via API

```powershell
$body = '{"url":"https://github.com/pallets/flask.git","name":"flask"}'
Invoke-WebRequest -Uri http://localhost:8000/ingest `
  -Method POST `
  -ContentType "application/json" `
  -Body $body `
  -UseBasicParsing
```

### Check ingestion status

```powershell
Invoke-WebRequest -Uri http://localhost:8000/ingest/flask/status -UseBasicParsing
# → {"repository":"flask","status":"done","summary":{...}}
```

---

## 9. Incremental Updates

When you pull new changes to an ingested repository and want to update the knowledge bases:

```powershell
# Pull latest changes
cd data\repositories\flask
git pull
cd ..\..\..

# Re-run ingest — only changed files and new commits are processed
.\.venv\Scripts\python.exe scripts/ingest_repo.py --local data\repositories\flask --name flask
```

The manifest at `data/repositories/flask/.archon_manifest.json` tracks what's already been indexed. On a re-run you will see something like:

```
Files: 5 changed/new, 225 unchanged, 0 deleted
New commits: 3
Vectors added: 22
```

Only the 22 new/changed chunks are sent to Qdrant. The 225 unchanged files are skipped entirely.

---

## 10. Understanding the Output

### Confidence Score

| Score | Meaning |
|---|---|
| 0.8 – 1.0 | Strong evidence — ADRs, explicit code, commit trail |
| 0.5 – 0.8 | Moderate evidence — inferred from code structure |
| 0.3 – 0.5 | Weak evidence — limited history or small repository |
| 0.0 – 0.3 | Very low — no ADRs, sparse code, placeholder mode |

A lower confidence does **not** mean the recommendation is wrong — it means the evidence base is thin. ARCHON will explicitly list what it couldn't find under **Uncertainties**.

### Evidence Types

| Type | Source |
|---|---|
| `code` | Actual source files parsed by AST/regex |
| `commit` | Git commit messages from history |
| `adr` | Architecture Decision Records found in `/docs/adr` etc. |
| `readme` | README.md and documentation files |
| `graph` | Relationships in the Neo4j dependency graph |
| `semantic` | Vector similarity results from Qdrant |

### Evidence Strength (Historian Agent)

| Label | Meaning |
|---|---|
| `CONFIRMED` | ADR, design doc, or explicit recorded decision |
| `INFERRED` | Detailed commit message or PR description |
| `UNKNOWN` | No explicit rationale found |

### Risk Levels

| Level | Meaning |
|---|---|
| 🟢 LOW | Minor issue, straightforward mitigation |
| 🟡 MEDIUM | Requires attention and planning |
| 🔴 HIGH | Significant impact, could affect users |
| 🔴 CRITICAL | Must address before proceeding |

---

## 11. Writing Good Queries

ARCHON works best with specific, action-oriented questions.

### Effective query patterns

```
Replace [technology A] with [technology B]
Migrate from [X] to [Y]
Remove the [component/dependency]
Add [new feature/service]
Split [monolith/service] into [microservices/components]
What depends on [component]?
What would break if [change]?
What are the security implications of [change]?
```

### Good examples

```
Replace Redis with DynamoDB. What are the impacts?
Migrate authentication from session-based to JWT tokens.
Remove the Celery task queue and replace with a direct database polling approach.
Add rate limiting middleware to all API endpoints.
What components depend on the PaymentService?
Split the UserService into separate Authentication and Profile services.
Move from SQLite to PostgreSQL for production.
Replace the monolithic Flask app with FastAPI microservices.
```

### Less effective examples

```
"Tell me about the code"           → too vague
"Is this code good?"               → not architectural
"Summarise the README"             → no change request
"Write new code for me"            → ARCHON analyses, doesn't generate
```

### Multi-part queries

You can ask compound questions:
```
Replace Jinja2 with Mako. What are the architectural impacts,
historical rationale for choosing Jinja2, and what security
implications does this change introduce?
```

ARCHON's 6 agents each specialise in a different dimension, so multi-part queries are naturally handled by the pipeline.

---

## 12. User Tweaks & Customisation

### 12.1 Switch LLM Model

Edit `.env`:
```env
GROQ_MODEL=openai/gpt-oss-120b     # more capable, slower
GROQ_MODEL=openai/gpt-oss-20b      # default, good balance
```

### 12.2 Customise Agent Prompts

Each agent reads its instructions from `app/prompts/<agent>.md`. You can edit these to:
- Change the output format
- Add domain-specific rules
- Restrict or expand what the agent considers

For example, to make the Security Agent focus on OWASP categories, add to `app/prompts/security.md`:
```markdown
## Additional Framework
Map all risks to OWASP Top 10 categories where applicable.
```

No code changes needed — just save the file and re-run.

### 12.3 Adjust Retrieval Depth

In `app/knowledge/graph_queries.py`, change the traversal depth for the Impact Agent:
```python
def get_impact_graph(component_name, repo_name, depth=4):  # increase for larger repos
```

In `app/knowledge/vector_search.py`, adjust how many evidence chunks are retrieved:
```python
def search_code(query, repository=None, top_k=8):   # increase for more evidence
def search_commits(query, repository=None, top_k=10):
```

### 12.4 Skip Heavy Files

In `app/ingestion/repository_loader.py`, add patterns to `SKIP_DIRS` or `SKIP_EXTS`:
```python
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "vendor", "generated"}
SKIP_EXTS = {".pyc", ".min.js", ".min.css", ".lock", ".pb"}  # add more as needed
```

### 12.5 Change the Chunk Size

In `app/ingestion/code_parser.py`:
```python
def chunk_file_content(file_info, chunk_size=400):  # lines per chunk
```

Smaller chunks = more precise retrieval but more vectors. Larger = fewer vectors but less precision. 200–500 lines is a good range.

### 12.6 Increase Git History Depth

In `app/ingestion/git_parser.py`:
```python
MAX_COMMITS = 200  # increase if you have rich commit history
```

### 12.7 Run with a Different Port

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 9000
```

### 12.8 Enable Verbose Logging

In `.env`:
```env
LOG_LEVEL=DEBUG
```

Or per-run:
```powershell
$env:LOG_LEVEL="DEBUG"; .\.venv\Scripts\python.exe scripts/test_archon.py --repo flask --query "..."
```

### 12.9 Save Analysis Output to a File

For a quick terminal dump:

```powershell
.\.venv\Scripts\python.exe scripts/test_archon.py --repo flask --query "Replace Redis with DynamoDB" > output.txt
```

For a fully formatted Markdown report with all sections, tables, and evidence, use the `--report` flag instead — see [Section 12.13](#1213-generate-a-markdown-analysis-report).

To save raw JSON programmatically:
```python
import json
from app.orchestrator.orchestrator import run_analysis

decision = run_analysis("flask", "Replace Jinja2 with Mako")
with open("result.json", "w") as f:
    json.dump(decision.model_dump(), f, indent=2)
```

### 12.10 Add a New Repository Without Cloning

If you already have the code locally:
```powershell
.\.venv\Scripts\python.exe scripts/ingest_repo.py --local "C:\projects\my-app" --name my-app
```

The repository does not need to be a git repo — ARCHON will skip git parsing gracefully and still index the code and dependencies.

### 12.11 Re-index Only Vectors (Keep Graph)

If you want to update semantic search without touching the Neo4j graph:
```powershell
.\.venv\Scripts\python.exe scripts/build_vectors.py --name flask --clear
```

### 12.12 Re-index Only the Graph (Keep Vectors)

```powershell
.\.venv\Scripts\python.exe scripts/build_graph.py --name flask
```

### 12.13 Generate a Markdown Analysis Report

After an analysis run, ARCHON can write a self-contained `.md` report file — identical in structure to the example `analysis_flask_jinja2_to_mako.md` in the project root.

**Enable it with the `--report` flag:**

```powershell
.\.venv\Scripts\python.exe scripts/test_archon.py `
  --repo flask `
  --query "Replace Jinja2 with Mako" `
  --report
```

Output:
```
  Generating Markdown report...
  ✓  Report saved to: C:\...\ARCHON1\analysis_flask_replace_jinja2_with_mako_a1b2c3d4.md
```

**Save to a custom directory:**

```powershell
.\.venv\Scripts\python.exe scripts/test_archon.py `
  --repo flask `
  --query "Replace Jinja2 with Mako" `
  --report `
  --report-dir "C:\reports"
```

**Combine with ingestion in one command:**

```powershell
.\.venv\Scripts\python.exe scripts/test_archon.py `
  --url https://github.com/pallets/flask.git `
  --ingest `
  --query "Replace Jinja2 with Mako" `
  --report
```

#### Report filename

The file is automatically named using the pattern:

```
analysis_<repo>_<query_slug>_<session_id>.md
```

For example: `analysis_flask_replace_jinja2_with_mako_a1b2c3d4.md`

#### What's in the report

| Section | Content source |
|---|---|
| **Header** | Session ID, processing time, confidence, date |
| **✅ Recommendation** | `decision.recommendation` |
| **🧠 Reasoning** | `decision.reasoning` (expanded via Groq if too short) |
| **💥 Impact** | Direct, indirect, API, config, testing, deployment impact tables |
| **🔒 Security** | Data-flow changes table + risks table with emoji levels |
| **📜 Historical Context** | Historian agent findings + key commit list |
| **🔀 Alternatives** | Ranked list of alternatives |
| **📋 Evidence Trail** | Numbered table of all evidence sources |
| **❓ Uncertainties** | Numbered list of what ARCHON couldn't determine |
| **📊 Agent Confidence** | Per-agent confidence score table |
| **🏗 Architecture Summary** | Ingestion counts + key components (when available) |

#### When Groq is used for the report

The report generator is **mostly programmatic** — it builds everything directly from the `ArchonDecision` object. Groq is called **only if** `decision.reasoning` is shorter than 200 characters (i.e. the synthesizer returned a very terse string). In that case, one additional Groq call expands it into a readable prose paragraph. If Groq is unavailable, the raw reasoning is used as-is.

#### Generate a report from Python

You can call the report generator directly from your own scripts:

```python
from scripts.test_archon import generate_report
from app.orchestrator.orchestrator import run_analysis
from pathlib import Path

decision = run_analysis("flask", "Replace Jinja2 with Mako")

report_path = generate_report(
    decision=decision,
    repo_name="flask",
    user_query="Replace Jinja2 with Mako",
    ingestion_summary=None,       # pass the ingest_repository() summary dict if available
    output_dir=Path("C:/reports"),
)
print(f"Report written to: {report_path}")
```

---

## 13. Troubleshooting

### Groq: model not found

```
Error: The model `llama-3.1-8b-instant` does not exist
```
**Fix:** Update `GROQ_MODEL` in `.env`. Run the test script to see available models:
```powershell
.\.venv\Scripts\python.exe -c "
from openai import OpenAI; import os; from dotenv import load_dotenv
load_dotenv()
c = OpenAI(api_key=os.getenv('GROQ_API_KEY'), base_url='https://api.groq.com/openai/v1')
[print(m.id) for m in c.models.list().data]
"
```

### Neo4j: Unauthorized

```
{neo4j_code: Neo.ClientError.Security.Unauthorized}
```
**Fix:** Both `NEO4J_USERNAME` and `NEO4J_DATABASE` must equal the instance ID (e.g. `a6bec2c3`), not `neo4j`. Check your AuraDB console.

### Qdrant: Index required

```
Bad request: Index required but not found for "repository"
```
**Fix:** The payload indexes need to be created. Run:
```powershell
.\.venv\Scripts\python.exe -c "
import app.knowledge.qdrant_client as q; q._qdrant_instance = None
from app.knowledge.qdrant_client import get_qdrant_client
c = get_qdrant_client()
print('Indexes created. Vectors:', c.count())
"
```

### Analysis returns placeholder responses

All agents say `"Add your Groq API key"`.  
**Fix:** Your `GROQ_API_KEY` in `.env` still starts with `PLACEHOLDER`. Add the real key and restart.

### Analysis is slow (60–120 seconds)

This is expected for the first run — the embedding model (`all-MiniLM-L6-v2`) loads from disk on first use. Subsequent runs in the same session are faster. To speed up:
- Use `openai/gpt-oss-20b` (faster than 120b)
- Reduce `top_k` in `vector_search.py`

### Port 8000 already in use

```powershell
netstat -ano | findstr :8000
# Note the PID in the last column, then:
taskkill /PID <pid> /F
```

Or use a different port:
```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8001
```

### ImportError or ModuleNotFoundError

```powershell
# Make sure venv is activated
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### sentence-transformers not installed

```
sentence-transformers not installed. Using zero-vector fallback.
```
This warning means semantic search works but with reduced accuracy.  
**Fix:**
```powershell
.\.venv\Scripts\pip.exe install sentence-transformers
```
Takes a few minutes (downloads ~500MB PyTorch model).

---

## 14. Frequently Asked Questions

**Q: Do I need all three API keys to use ARCHON?**  
A: No. With just Groq, you get LLM reasoning over whatever semantic evidence is in memory. Neo4j adds dependency graph traversal (impact tracing). Qdrant persists semantic evidence across restarts. For real production-quality analysis, all three are recommended.

**Q: Will ARCHON work on private repositories?**  
A: Yes, use `--local` to point to a local clone. No data leaves your machine except for LLM calls to Groq and writes to your own Neo4j/Qdrant instances.

**Q: How large a repository can ARCHON handle?**  
A: Tested up to ~500MB repositories. The `MAX_REPO_SIZE_MB` setting in `.env` controls the guard. Files larger than 500KB are automatically skipped. Very large repos (Linux kernel, etc.) will work but ingestion will be slow — start with focused subdirectories.

**Q: Can I analyse multiple repositories?**  
A: Yes. Ingest each one separately with different names. Every analysis query specifies which repository to use. Nodes in Neo4j and chunks in Qdrant are all tagged with `repository` so they never mix.

**Q: Why does the Historian Agent sometimes have low confidence?**  
A: Because most repositories don't have ADRs. Without explicit decision records, the historian can only infer rationale from commit messages — which is marked as `INFERRED` and scored lower. Adding ADRs to your repository dramatically improves historian quality.

**Q: Can I add my own agents?**  
A: Yes. Create a new file in `app/agents/`, add a prompt in `app/prompts/`, add a new node to the LangGraph pipeline in `app/orchestrator/graph.py`, and add the corresponding field to `ArchonState` in `app/models/state.py`.

**Q: Can ARCHON save its analysis to a file?**  
A: Yes. Pass `--report` to `test_archon.py` and a fully formatted Markdown report is written to the project root (or any directory you specify with `--report-dir`). The file name follows the pattern `analysis_<repo>_<query_slug>_<session_id>.md`. See [Section 12.13](#1213-generate-a-markdown-analysis-report) for full details.

**Q: Does re-ingesting overwrite my Neo4j data?**  
A: No. Neo4j uses `MERGE` throughout, so re-ingesting adds new nodes/edges without duplicating existing ones. Only deleted files are explicitly removed from the graph.

**Q: How do I reset everything for a fresh start?**  
A: Delete the manifest file and clear Qdrant:
```powershell
# Delete manifest
Remove-Item "data\repositories\<name>\.archon_manifest.json"

# Clear Neo4j (run in Neo4j browser or Cypher)
# MATCH (n {repository: "<name>"}) DETACH DELETE n

# Clear Qdrant vectors
.\.venv\Scripts\python.exe -c "
from app.knowledge.qdrant_client import get_qdrant_client
get_qdrant_client().delete_by_repository('<name>')
"

# Then re-ingest
.\.venv\Scripts\python.exe scripts/ingest_repo.py --local data\repositories\<name> --name <name> --force
```

---

*ARCHON User Guide — Generated for ARCHON v1.0 | Python 3.13 | Windows*
