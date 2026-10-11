"""
ADR Parser
Finds Architecture Decision Records in a repository.
Common locations: /docs/adr/, /adr/, /docs/decisions/, /docs/architecture/
"""
import logging
import re
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

ADR_DIRS = ["adr", "docs/adr", "docs/decisions", "docs/architecture", "architecture"]
ADR_PATTERNS = [
    re.compile(r"^ADR[-_]?\d+", re.IGNORECASE),
    re.compile(r"^\d{4}[-_]", re.IGNORECASE),   # MADR style: 0001-title.md
]


def find_adrs(repo_path: Path) -> List[Dict[str, Any]]:
    """Locate and parse all ADRs in a repository."""
    adrs = []

    # Search known ADR directories
    for adr_dir in ADR_DIRS:
        target = repo_path / adr_dir
        if target.exists() and target.is_dir():
            for f in target.rglob("*.md"):
                adr = _parse_adr_file(f, repo_path)
                if adr:
                    adrs.append(adr)

    # Search root and docs for ADR-named files
    for f in repo_path.rglob("*.md"):
        if any(p.match(f.stem) for p in ADR_PATTERNS):
            adr = _parse_adr_file(f, repo_path)
            if adr and adr not in adrs:
                adrs.append(adr)

    logger.info("Found %d ADRs in %s", len(adrs), repo_path.name)
    return adrs


def _parse_adr_file(path: Path, repo_path: Path) -> Dict[str, Any]:
    """Parse a single ADR markdown file."""
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        rel_path = str(path.relative_to(repo_path)).replace("\\", "/")

        # Extract title from first heading
        title_match = re.search(r"^#+\s+(.+)", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else path.stem

        # Try to extract status
        status_match = re.search(r"Status[:\s]+(\w+)", content, re.IGNORECASE)
        status = status_match.group(1) if status_match else "unknown"

        return {
            "id": path.stem,
            "title": title,
            "status": status,
            "file": rel_path,
            "content": content[:3000],  # Cap to avoid huge payloads
        }
    except Exception as e:
        logger.debug("Failed to parse ADR file %s: %s", path, e)
        return {}
