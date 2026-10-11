"""
Change Impact Agent
Determines direct and indirect impact of a proposed change using the dependency graph.
"""
import json
import logging

from app.agents._base import load_prompt, safe_json_parse
from app.knowledge.graph_queries import get_impact_graph, get_repo_summary_text
from app.knowledge.vector_search import search_code, format_evidence_for_prompt
from app.llm.groq_client import ask_groq_json
from app.models.state import ArchonState

logger = logging.getLogger(__name__)

FALLBACK = {
    "change_requested": "",
    "direct_impact": [],
    "indirect_impact": [],
    "api_impact": [],
    "data_impact": [],
    "config_impact": [],
    "testing_impact": [],
    "deployment_impact": [],
    "evidence": [],
    "confidence": 0.0,
}


def impact_agent(state: ArchonState) -> ArchonState:
    """
    Change Impact Agent node.
    Populates state["impact_findings"].
    """
    logger.info("[ImpactAgent] Starting analysis")
    errors = state.get("errors", [])
    repo_name = state.get("repository_name", "")
    user_query = state.get("user_query", "")
    repo_findings = state.get("repository_findings", {})
    arch_findings = state.get("architecture_findings", {})

    try:
        # Extract the component being changed
        target_component = _extract_target_component(user_query, repo_findings)

        # 1. Graph evidence — dependency traversal
        impact_paths = get_impact_graph(target_component, repo_name, depth=4)
        graph_text = json.dumps(impact_paths, indent=2)[:3000]

        # 2. Semantic evidence — code using the target component
        code_results = search_code(target_component, repository=repo_name, top_k=10)
        code_evidence = format_evidence_for_prompt(code_results, max_chars=2000)

        # 3. Build prompt
        system_prompt = load_prompt("impact")

        repo_summary = json.dumps(repo_findings, indent=2)[:1500]
        arch_summary = json.dumps(arch_findings, indent=2)[:1500]

        user_prompt = f"""
## Repository
{repo_name}

## Developer Query (Proposed Change)
{user_query}

## Target Component
{target_component}

## Dependency Graph Paths (from Neo4j)
{graph_text}

## Repository Findings Summary
{repo_summary}

## Architecture Findings Summary
{arch_summary}

## Code Evidence (from Qdrant - files using {target_component})
{code_evidence}

Determine all direct and indirect impacts of this change. Return structured JSON findings.
"""
        result = ask_groq_json(system_prompt, user_prompt)
        findings = result if isinstance(result, dict) else safe_json_parse(str(result), FALLBACK)

        # Set the change_requested field
        findings["change_requested"] = user_query

        logger.info(
            "[ImpactAgent] Done. Direct: %d, Indirect: %d",
            len(findings.get("direct_impact", [])),
            len(findings.get("indirect_impact", [])),
        )

    except Exception as e:
        logger.error("[ImpactAgent] Error: %s", e)
        errors.append(f"ImpactAgent error: {e}")
        findings = {**FALLBACK, "change_requested": user_query, "error": str(e)}

    state["impact_findings"] = findings
    state["errors"] = errors
    return state


def _extract_target_component(query: str, repo_findings: dict) -> str:
    """Identify the primary component being changed."""
    import re
    # Look for 'Replace X with Y' or 'migrate X' or 'remove X' patterns
    patterns = [
        r"[Rr]eplace\s+(\w+)",
        r"[Mm]igrate\s+(?:from\s+)?(\w+)",
        r"[Rr]emove\s+(\w+)",
        r"[Ss]witch\s+(?:from\s+)?(\w+)",
        r"[Uu]pgrade\s+(\w+)",
        r"[Uu]pdate\s+(\w+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, query)
        if m:
            return m.group(1)

    # Fallback: look in repo findings components
    components = repo_findings.get("components", [])
    for comp in components:
        name = comp.get("name", "")
        if name and name.lower() in query.lower():
            return name

    # Last resort: first capitalized word after certain keywords
    m = re.search(r"\b(Redis|PostgreSQL|MySQL|MongoDB|DynamoDB|Kafka|RabbitMQ|nginx|docker)\b", query, re.IGNORECASE)
    if m:
        return m.group(1)

    return query.split()[0] if query else "unknown"
