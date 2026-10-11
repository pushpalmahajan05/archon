"""
Git Parser
Extracts commit history from a repository using GitPython.
"""
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

MAX_COMMITS = 200  # Limit to avoid huge indexing times


def parse_git_history(repo_path: Path) -> List[Dict[str, Any]]:
    """
    Extract commits from the repository.
    Returns list of dicts: {hash, author, date, message}
    """
    from git import Repo

    commits = []
    try:
        repo = Repo(repo_path)
        for i, commit in enumerate(repo.iter_commits()):
            if i >= MAX_COMMITS:
                break
            commits.append({
                "hash": commit.hexsha[:8],
                "author": str(commit.author),
                "date": str(commit.authored_datetime),
                "message": commit.message.strip(),
            })
    except Exception as e:
        logger.error("Failed to parse git history: %s", e)
    return commits
