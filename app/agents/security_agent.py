"""
Security Analysis Agent
Analyzes security implications of a proposed architectural change.
"""
import json
import logging

from app.agents._base import load_prompt, safe_json_parse
from app.knowledge.vector_search import search_code, search_docs, format_evidence_for_prompt
from app.llm.groq_client import ask_groq_json
from app.models.state import ArchonState

logger = logging.getLogger(__name__)

FALLBACK = {
    "security_impact_summary": "Insufficient evidence for security analysis.",
    "data_flow_changes": [],
    "trust_boundary_changes": [],
    "access_control": [],
    "authentication": "Unknown",
    "authorization": "Unknown",
    "secrets": [],
    "risks": [],
    "evidence": [],
    "confidence": 0.0,
}


def security_agent(state: ArchonState) -> ArchonState:
    """
    Security Analysis Agent node.
    Populates state["security_findings"].
    """
    logger.info("[SecurityAgent] Starting analysis")
    errors = state.get("errors", [])
    repo_name = state.get("repository_name", "")
    user_query = state.get("user_query", "")
    arch_findings = state.get("architecture_findings", {})
    impact_findings = state.get("impact_findings", {})

    try:
        # 1. Semantic evidence — security-relevant code
        auth_results = search_code("authentication authorization security credentials", repository=repo_name, top_k=5)
        config_results = search_code("config env secret key password token", repository=repo_name, top_k=5)
        auth_evidence = format_evidence_for_prompt(auth_results, max_chars=1500)
        config_evidence = format_evidence_for_prompt(config_results, max_chars=1000)

        # 2. Build prompt
        system_prompt = load_prompt("security")

        arch_summary = json.dumps(arch_findings, indent=2)[:1500]
        impact_summary = json.dumps(impact_findings, indent=2)[:1500]

        user_prompt = f"""
## Repository
{repo_name}

## Developer Query (Proposed Change)
{user_query}

## Architecture Findings
{arch_summary}

## Impact Findings
{impact_summary}

## Authentication/Authorization Code Evidence (from Qdrant)
{auth_evidence}

## Configuration/Secrets Evidence (from Qdrant)
{config_evidence}

Analyze security implications of the proposed change. Return structured JSON findings.
"""
        result = ask_groq_json(system_prompt, user_prompt)
        findings = result if isinstance(result, dict) else safe_json_parse(str(result), FALLBACK)

        logger.info(
            "[SecurityAgent] Done. Risks found: %d", len(findings.get("risks", []))
        )

    except Exception as e:
        logger.error("[SecurityAgent] Error: %s", e)
        errors.append(f"SecurityAgent error: {e}")
        findings = {**FALLBACK, "error": str(e)}

    state["security_findings"] = findings
    state["errors"] = errors
    return state
