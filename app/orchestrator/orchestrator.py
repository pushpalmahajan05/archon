"""
ARCHON Orchestrator
Entry point for running a full analysis pipeline.
Initialises the shared state and invokes the LangGraph pipeline.
"""
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.models.state import ArchonState
from app.models.decision import ArchonDecision
from app.orchestrator.graph import get_graph

logger = logging.getLogger(__name__)


def run_analysis(
    repository_name: str,
    user_query: str,
    repository_path: Optional[str] = None,
) -> ArchonDecision:
    """
    Run the full ARCHON analysis pipeline.

    Args:
        repository_name: Slug/name of the repository (must already be ingested).
        user_query:       The developer's change request in natural language.
        repository_path:  Optional local path (for display purposes only).

    Returns:
        ArchonDecision with recommendation, evidence, confidence, etc.
    """
    session_id = str(uuid.uuid4())[:8]
    started_at = datetime.now(timezone.utc).isoformat()

    logger.info(
        "[Orchestrator] session=%s repo=%s query=%s",
        session_id,
        repository_name,
        user_query[:80],
    )

    # Initialise shared state
    initial_state: ArchonState = {
        "repository_path": repository_path or "",
        "repository_name": repository_name,
        "user_query": user_query,
        "plan": [
            "repository",
            "architecture",
            "historian",
            "impact",
            "security",
            "synthesizer",
        ],
        "repository_findings": {},
        "architecture_findings": {},
        "history_findings": {},
        "impact_findings": {},
        "security_findings": {},
        "final_decision": {},
        "evidence": [],
        "errors": [],
        "session_id": session_id,
        "started_at": started_at,
    }

    start_time = time.time()

    try:
        graph = get_graph()
        final_state: ArchonState = graph.invoke(initial_state)
    except Exception as e:
        logger.error("[Orchestrator] Pipeline failed: %s", e)
        final_state = {**initial_state, "errors": [str(e)]}

    elapsed = round(time.time() - start_time, 2)
    decision_raw = final_state.get("final_decision", {})

    # Build the structured decision
    decision = ArchonDecision(
        query=user_query,
        repository=repository_name,
        recommendation=decision_raw.get(
            "recommendation",
            "Analysis could not be completed. Check errors.",
        ),
        reasoning=decision_raw.get("reasoning", ""),
        alternatives=[
            alt.get("option", str(alt)) if isinstance(alt, dict) else str(alt)
            for alt in decision_raw.get("alternatives", [])
        ],
        affected_components=decision_raw.get("affected_components", []),
        direct_impact=[
            item.get("component", str(item)) if isinstance(item, dict) else str(item)
            for item in final_state.get("impact_findings", {}).get("direct_impact", [])
        ],
        indirect_impact=[
            item.get("component", str(item)) if isinstance(item, dict) else str(item)
            for item in final_state.get("impact_findings", {}).get("indirect_impact", [])
        ],
        historical_context=decision_raw.get("historical_context", ""),
        security_implications=decision_raw.get("security_implications", []),
        risks=decision_raw.get("risks", []),
        evidence=decision_raw.get("evidence", []),
        uncertainties=decision_raw.get("uncertainties", []),
        confidence=float(decision_raw.get("confidence", 0.0)),
        agent_findings=decision_raw.get("agent_findings", {}),
        session_id=session_id,
        processing_time_seconds=elapsed,
    )

    if final_state.get("errors"):
        logger.warning(
            "[Orchestrator] session=%s completed with %d errors: %s",
            session_id,
            len(final_state["errors"]),
            final_state["errors"],
        )

    logger.info(
        "[Orchestrator] session=%s done in %.2fs confidence=%.2f",
        session_id,
        elapsed,
        decision.confidence,
    )

    return decision
