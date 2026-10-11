"""
ARCHON Decision Model
The structured output produced by the Decision Synthesizer.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class RiskLevel(str):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Risk(BaseModel):
    description: str
    level: str          # LOW | MEDIUM | HIGH | CRITICAL
    mitigation: Optional[str] = None


class AgentFindings(BaseModel):
    """Generic container for any agent's structured findings."""
    agent: str
    summary: str
    details: Dict[str, Any] = {}
    evidence: List[Dict[str, Any]] = []
    confidence: float = 0.0
    errors: List[str] = []


class ArchonDecision(BaseModel):
    """Final output of the ARCHON pipeline."""
    query: str
    repository: str

    # Core recommendation
    recommendation: str
    reasoning: str
    alternatives: List[str] = []

    # Impact
    affected_components: List[str] = []
    direct_impact: List[str] = []
    indirect_impact: List[str] = []

    # Historical context
    historical_context: str = ""

    # Security
    security_implications: List[str] = []

    # Risks and mitigations
    risks: List[Risk] = []

    # Evidence
    evidence: List[Dict[str, Any]] = []

    # Uncertainties
    uncertainties: List[str] = []

    # Confidence
    confidence: float = 0.0

    # Raw agent findings
    agent_findings: Dict[str, Any] = {}

    # Metadata
    session_id: Optional[str] = None
    processing_time_seconds: Optional[float] = None
