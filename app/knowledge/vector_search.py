"""
Vector Search Helpers
Higher-level Qdrant queries for agent consumption.
"""
from typing import Any, Dict, List, Optional

from app.knowledge.qdrant_client import get_qdrant_client


def search_evidence(
    query: str,
    repository: Optional[str] = None,
    evidence_type: Optional[str] = None,
    top_k: int = 10,
) -> List[Dict[str, Any]]:
    """Search for semantically relevant evidence."""
    qdrant = get_qdrant_client()
    return qdrant.search(query, repository=repository, evidence_type=evidence_type, top_k=top_k)


def search_code(query: str, repository: Optional[str] = None, top_k: int = 8) -> List[Dict]:
    return search_evidence(query, repository=repository, evidence_type="code", top_k=top_k)


def search_adrs(query: str, repository: Optional[str] = None, top_k: int = 5) -> List[Dict]:
    return search_evidence(query, repository=repository, evidence_type="adr", top_k=top_k)


def search_commits(query: str, repository: Optional[str] = None, top_k: int = 10) -> List[Dict]:
    return search_evidence(query, repository=repository, evidence_type="commit", top_k=top_k)


def search_docs(query: str, repository: Optional[str] = None, top_k: int = 5) -> List[Dict]:
    return search_evidence(query, repository=repository, evidence_type="readme", top_k=top_k)


def format_evidence_for_prompt(results: List[Dict], max_chars: int = 3000) -> str:
    """Format retrieved evidence chunks into a readable string for agent prompts."""
    if not results:
        return "No relevant evidence found."

    lines = []
    total = 0
    for i, r in enumerate(results, 1):
        src = r.get("file", r.get("source", "unknown"))
        etype = r.get("type", "unknown")
        score = r.get("score", 0.0)
        text = r.get("text", "")[:500]

        chunk = f"[{i}] {etype.upper()} | {src} (relevance: {score:.2f})\n{text}\n"
        if total + len(chunk) > max_chars:
            break
        lines.append(chunk)
        total += len(chunk)

    return "\n".join(lines)
