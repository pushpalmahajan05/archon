"""
Decision Synthesizer Agent
Combines all agent findings into the final evidence-backed recommendation.
"""
import json
import logging

from app.agents._base import load_prompt, safe_json_parse
from app.knowledge.vector_search import search_evidence, format_evidence_for_prompt
from app.llm.groq_client import ask_groq_json
from app.models.state import ArchonState

logger = logging.getLogger(__name__)

FALLBACK = {
    "recommendation": "Insufficient evidence to make a recommendation.",
    "reasoning": "",
    "alternatives": [],
    "affected_components": [],
    "historical_context": "",
    "security_implications": [],
    "risks": [],
    "evidence": [],
    "uncertainties": [],
    "confidence": 0.0,
}


def synthesizer_agent(state: ArchonState) -> ArchonState:
    """
    Decision Synthesizer Agent node.
    Populates state["final_decision"].
    """
    logger.info("[SynthesizerAgent] Starting synthesis")
    errors = state.get("errors", [])
    repo_name = state.get("repository_name", "")
    user_query = state.get("user_query", "")

    repo_findings = state.get("repository_findings", {})
    arch_findings = state.get("architecture_findings", {})
    history_findings = state.get("history_findings", {})
    impact_findings = state.get("impact_findings", {})
    security_findings = state.get("security_findings", {})

    try:
        # Final semantic search for cross-cutting evidence
        final_evidence = search_evidence(user_query, repository=repo_name, top_k=8)
        evidence_text = format_evidence_for_prompt(final_evidence, max_chars=2000)

        # Build prompt
        system_prompt = load_prompt("synthesizer")

        def _truncate(obj, chars=1200):
            return json.dumps(obj, indent=2)[:chars]

        user_prompt = f"""
## Repository
{repo_name}

## Developer Query
{user_query}

## Repository Intelligence Findings
{_truncate(repo_findings)}

## Architecture Reconstruction Findings
{_truncate(arch_findings)}

## Decision Historian Findings
{_truncate(history_findings)}

## Change Impact Findings
{_truncate(impact_findings)}

## Security Analysis Findings
{_truncate(security_findings)}

## Additional Semantic Evidence (from Qdrant)
{evidence_text}

Synthesize all findings into a final evidence-backed architectural recommendation.
Return structured JSON.
"""
        result = ask_groq_json(system_prompt, user_prompt)
        decision = result if isinstance(result, dict) else safe_json_parse(str(result), FALLBACK)

        logger.info(
            "[SynthesizerAgent] Done. Confidence: %.2f", decision.get("confidence", 0.0)
        )

    except Exception as e:
        logger.error("[SynthesizerAgent] Error: %s", e)
        errors.append(f"SynthesizerAgent error: {e}")
        decision = {**FALLBACK, "error": str(e)}

    # Attach raw agent findings for traceability
    decision["agent_findings"] = {
        "repository": repo_findings,
        "architecture": arch_findings,
        "history": history_findings,
        "impact": impact_findings,
        "security": security_findings,
    }

    state["final_decision"] = decision
    state["errors"] = errors
    return state
