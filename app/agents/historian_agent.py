"""
Decision Historian Agent
Finds ADRs, commits, PRs, issues and recovers "why" decisions were made.
"""
import json
import logging

from app.agents._base import load_prompt, safe_json_parse
from app.knowledge.graph_queries import get_history_graph
from app.knowledge.vector_search import search_adrs, search_commits, format_evidence_for_prompt
from app.llm.groq_client import ask_groq_json
from app.models.state import ArchonState

logger = logging.getLogger(__name__)

FALLBACK = {
    "decisions": [],
    "overall_confidence": 0.0,
}


def historian_agent(state: ArchonState) -> ArchonState:
    """
    Decision Historian Agent node.
    Populates state["history_findings"].
    """
    logger.info("[HistorianAgent] Starting analysis")
    errors = state.get("errors", [])
    repo_name = state.get("repository_name", "")
    user_query = state.get("user_query", "")

    try:
        # Extract the key technology from query (e.g., "Redis", "PostgreSQL")
        keyword = _extract_keyword(user_query)

        # 1. Graph evidence — ADRs and commits
        history_graph = get_history_graph(repo_name, keyword)
        graph_text = json.dumps(history_graph, indent=2)[:3000]

        # 2. Semantic evidence
        adr_results = search_adrs(user_query, repository=repo_name, top_k=5)
        commit_results = search_commits(user_query, repository=repo_name, top_k=8)
        adr_evidence = format_evidence_for_prompt(adr_results, max_chars=2000)
        commit_evidence = format_evidence_for_prompt(commit_results, max_chars=1500)

        # 3. Build prompt
        system_prompt = load_prompt("historian")

        user_prompt = f"""
## Repository
{repo_name}

## Developer Query
{user_query}

## ADRs and Commits (from Neo4j)
{graph_text}

## ADR Evidence (from Qdrant)
{adr_evidence}

## Commit Evidence (from Qdrant)
{commit_evidence}

Recover historical decision rationale and return structured JSON findings.
"""
        result = ask_groq_json(system_prompt, user_prompt)
        findings = result if isinstance(result, dict) else safe_json_parse(str(result), FALLBACK)

        logger.info(
            "[HistorianAgent] Done. Decisions found: %d", len(findings.get("decisions", []))
        )

    except Exception as e:
        logger.error("[HistorianAgent] Error: %s", e)
        errors.append(f"HistorianAgent error: {e}")
        findings = {**FALLBACK, "error": str(e)}

    state["history_findings"] = findings
    state["errors"] = errors
    return state


def _extract_keyword(query: str) -> str:
    """Extract the primary technology/component name from the query."""
    import re
    # Look for capitalized technology names
    words = re.findall(r"\b[A-Z][a-z]+[A-Z]?\w*\b", query)
    if words:
        return words[0]
    # Fallback: first meaningful word
    stopwords = {"what", "how", "why", "where", "when", "replace", "with", "the", "a", "an"}
    for word in query.lower().split():
        if word not in stopwords and len(word) > 3:
            return word
    return query[:50]
