"""
ARCHON Evidence Model
Every claim in ARCHON must trace back to an Evidence record.
"""
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel


class EvidenceType(str, Enum):
    CODE = "code"
    ADR = "adr"
    COMMIT = "commit"
    ISSUE = "issue"
    README = "readme"
    CONFIG = "config"
    GRAPH = "graph"
    SEMANTIC = "semantic"
    DOCUMENTATION = "documentation"


class Evidence(BaseModel):
    """A single traceable piece of evidence."""
    source: str                        # File path, ADR id, commit hash, etc.
    evidence_type: EvidenceType
    content: str                       # The actual text snippet
    repository: Optional[str] = None
    file_path: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    symbol: Optional[str] = None       # function/class name if code
    commit_hash: Optional[str] = None
    confidence: float = 1.0
    metadata: dict = {}


class EvidencedClaim(BaseModel):
    """A claim with supporting evidence — prevents hallucination."""
    claim: str
    evidence: List[Evidence]
    confidence: float = 0.0
    certainty: str = "INFERRED"        # CONFIRMED | INFERRED | UNKNOWN
