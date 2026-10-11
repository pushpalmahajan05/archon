"""
ARCHON FastAPI Application
Exposes the analysis pipeline and repository ingestion over HTTP.
"""
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import settings
from app.orchestrator.orchestrator import run_analysis

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ARCHON",
    description="Agentic Change-Impact Analysis System",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend — works with plain index.html (no build step)
_frontend_dir = Path(__file__).parent.parent / "frontend"
_frontend_dist = _frontend_dir / "dist"
# Use dist/ if it exists (built app), otherwise serve directly from frontend/
_static_dir = _frontend_dist if _frontend_dist.exists() else _frontend_dir
if _static_dir.exists():
    app.mount("/ui", StaticFiles(directory=str(_static_dir), html=True), name="frontend")


# ── Request / Response schemas ─────────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    repository: str
    query: str


class IngestRequest(BaseModel):
    url: Optional[str] = None          # Remote git URL
    local_path: Optional[str] = None   # Or a local directory path
    name: Optional[str] = None         # Override the repository slug


class IngestStatus(BaseModel):
    repository: str
    status: str
    summary: Optional[dict] = None
    error: Optional[str] = None


# In-memory ingestion status tracker (good enough for prototyping)
_ingest_jobs: dict[str, IngestStatus] = {}


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Basic health check."""
    return {"status": "ok", "model": settings.groq_model}


@app.get("/repositories")
def list_repositories():
    """List all repositories that have been ingested."""
    repos_dir = settings.repos_dir
    if not repos_dir.exists():
        return {"repositories": []}
    repos = [
        d.name for d in repos_dir.iterdir() if d.is_dir()
    ]
    return {"repositories": repos}


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    """
    Run the full ARCHON analysis pipeline for a change request.

    Example:
        POST /analyze
        {
          "repository": "redis-microservices-demo",
          "query": "Replace Redis with DynamoDB. What are the impacts?"
        }
    """
    logger.info("POST /analyze repo=%s query=%s", req.repository, req.query[:60])

    try:
        decision = run_analysis(
            repository_name=req.repository,
            user_query=req.query,
        )
        return decision.model_dump()
    except Exception as e:
        logger.error("Analysis failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest")
def ingest(req: IngestRequest, background_tasks: BackgroundTasks):
    """
    Ingest a repository into Neo4j + Qdrant.
    Runs in the background; poll /ingest/{name}/status for progress.
    """
    from app.ingestion.repository_loader import clone_repository, get_local_repo
    from app.ingestion.indexer import ingest_repository

    # Determine repo name
    if req.name:
        name = req.name
    elif req.url:
        name = req.url.rstrip("/").split("/")[-1].replace(".git", "")
    elif req.local_path:
        name = Path(req.local_path).name
    else:
        raise HTTPException(status_code=400, detail="Provide url or local_path.")

    if name in _ingest_jobs and _ingest_jobs[name].status == "running":
        return {"message": f"Ingestion already running for {name}", "name": name}

    _ingest_jobs[name] = IngestStatus(repository=name, status="running")

    def _run():
        try:
            if req.url:
                repo_path = clone_repository(req.url, name)
            else:
                repo_path = get_local_repo(req.local_path)

            summary = ingest_repository(repo_path, name)
            _ingest_jobs[name] = IngestStatus(
                repository=name, status="done", summary=summary
            )
        except Exception as e:
            logger.error("Ingestion failed for %s: %s", name, e)
            _ingest_jobs[name] = IngestStatus(
                repository=name, status="failed", error=str(e)
            )

    background_tasks.add_task(_run)
    return {"message": f"Ingestion started for {name}", "name": name}


@app.get("/ingest/{name}/status")
def ingest_status(name: str):
    """Poll the ingestion status for a repository."""
    if name not in _ingest_jobs:
        raise HTTPException(status_code=404, detail=f"No ingestion job found for {name}")
    return _ingest_jobs[name]


@app.get("/")
def root():
    """Serve the frontend index if present, else return API info."""
    index = _static_dir / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {
        "name": "ARCHON",
        "description": "Agentic Change-Impact Analysis System",
        "docs": "/docs",
        "health": "/health",
        "ui": "/ui",
    }
