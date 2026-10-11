"""
ARCHON Shared State
Passed through the LangGraph pipeline — every agent reads and writes this.
"""
from typing import TypedDict, List, Dict, Any, Optional


class ArchonState(TypedDict, total=False):
    # Input
    repository_path: str          # Local path to the cloned repository
    repository_name: str          # Name / slug of the repository
    user_query: str               # Developer's change request

    # Orchestrator plan
    plan: List[str]               # Ordered list of agents to invoke

    # Agent findings — each agent populates its own key
    repository_findings: Dict[str, Any]
    architecture_findings: Dict[str, Any]
    history_findings: Dict[str, Any]
    impact_findings: Dict[str, Any]
    security_findings: Dict[str, Any]

    # Final output
    final_decision: Dict[str, Any]

    # Shared evidence bag — agents can append raw evidence here
    evidence: List[Dict[str, Any]]

    # Error log — agents append errors without stopping the pipeline
    errors: List[str]

    # Session metadata
    session_id: str
    started_at: str
