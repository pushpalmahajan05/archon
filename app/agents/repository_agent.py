"""
Repository Intelligence Agent
Understands files, classes, functions, imports, dependencies, configs.
"""
import logging
from typing import Any, Dict

from app.agents._base import load_prompt, safe_json_parse
from app.knowledge.graph_queries import get_repo_summary_text
from app.knowledge.vector_search import search_code, search_docs, format_evidence_for_prompt
from app.llm.groq_client import ask_groq_json
from app.models.state import ArchonState

logger = logging.getLogger(__name__)

FALLBACK = {
    "components": [],
    "dependencies": [],
    "apis": [],
    "configuration": [],
    "observations": "Insufficient evidence.",
    "evidence": [],
    "confidence": 0.0,
}


def repository_agent(state: ArchonState) -> ArchonState:
    """
    Repository Intelligence Agent node.
    Populates state["repository_findings"].
    """
    logger.info("[RepositoryAgent] Starting analysis")
    errors = state.get("errors", [])

    repo_name = state.get("repository_name", "")
    user_query = state.get("user_query", "")

    try:
        # 1. Graph evidence — structural summary
        graph_summary = get_repo_summary_text(repo_name)

        # 2. Semantic evidence — relevant code and docs
        code_results = search_code(user_query, repository=repo_name, top_k=8)
        doc_results = search_docs(user_query, repository=repo_name, top_k=3)
        code_evidence = format_evidence_for_prompt(code_results, max_chars=2000)
        doc_evidence = format_evidence_for_prompt(doc_results, max_chars=1000)

        # 3. Build prompt
        system_prompt = load_prompt("repository")

        user_prompt = f"""
## Repository
{repo_name}

## Developer Query
{user_query}

## Graph Summary (from Neo4j)
{graph_summary}

## Code Evidence (from Qdrant)
{code_evidence}

## Documentation Evidence (from Qdrant)
{doc_evidence}

Analyze the repository and return structured JSON findings.
"""
        # 4. Ask LLM
        result = ask_groq_json(system_prompt, user_prompt)

        # 5. Validate and store
        findings = safe_json_parse(str(result) if isinstance(result, str) else "", FALLBACK)
        if isinstance(result, dict):
            findings = result

        logger.info(
            "[RepositoryAgent] Done. Confidence: %.2f", findings.get("confidence", 0.0)
        )

    except Exception as e:
        logger.error("[RepositoryAgent] Error: %s", e)
        errors.append(f"RepositoryAgent error: {e}")
        findings = {**FALLBACK, "error": str(e)}

    state["repository_findings"] = findings
    state["errors"] = errors
    return state
