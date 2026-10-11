"""
Architecture Reconstruction Agent
Reconstructs services, components, layers, and architectural relationships.
"""
import json
import logging

from app.agents._base import load_prompt, safe_json_parse
from app.knowledge.graph_queries import get_architecture_graph
from app.knowledge.vector_search import search_code, search_docs, format_evidence_for_prompt
from app.llm.groq_client import ask_groq_json
from app.models.state import ArchonState

logger = logging.getLogger(__name__)

FALLBACK = {
    "architectural_style": "unknown",
    "components": [],
    "component_relationships": [],
    "data_stores": [],
    "external_systems": [],
    "communication_patterns": [],
    "uncertainty": [],
    "evidence": [],
    "confidence": 0.0,
}


def architecture_agent(state: ArchonState) -> ArchonState:
    """
    Architecture Reconstruction Agent node.
    Populates state["architecture_findings"].
    """
    logger.info("[ArchitectureAgent] Starting analysis")
    errors = state.get("errors", [])
    repo_name = state.get("repository_name", "")
    user_query = state.get("user_query", "")
    repo_findings = state.get("repository_findings", {})

    try:
        # 1. Graph evidence — architecture graph
        arch_graph = get_architecture_graph(repo_name)
        graph_text = json.dumps(arch_graph, indent=2)[:3000]

        # 2. Semantic evidence
        arch_results = search_code(f"architecture service {user_query}", repository=repo_name, top_k=6)
        docker_results = search_code("docker service container", repository=repo_name, top_k=3)
        arch_evidence = format_evidence_for_prompt(arch_results, max_chars=1500)
        docker_evidence = format_evidence_for_prompt(docker_results, max_chars=1000)

        # 3. Build prompt
        system_prompt = load_prompt("architecture")

        repo_summary = json.dumps(repo_findings, indent=2)[:2000]

        user_prompt = f"""
## Repository
{repo_name}

## Developer Query
{user_query}

## Repository Findings (from Repository Agent)
{repo_summary}

## Architecture Graph (from Neo4j)
{graph_text}

## Architecture Code Evidence (from Qdrant)
{arch_evidence}

## Docker/Config Evidence (from Qdrant)
{docker_evidence}

Reconstruct the software architecture and return structured JSON findings.
"""
        result = ask_groq_json(system_prompt, user_prompt)
        findings = result if isinstance(result, dict) else safe_json_parse(str(result), FALLBACK)

        logger.info(
            "[ArchitectureAgent] Done. Confidence: %.2f", findings.get("confidence", 0.0)
        )

    except Exception as e:
        logger.error("[ArchitectureAgent] Error: %s", e)
        errors.append(f"ArchitectureAgent error: {e}")
        findings = {**FALLBACK, "error": str(e)}

    state["architecture_findings"] = findings
    state["errors"] = errors
    return state
