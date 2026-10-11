"""
Repository Loader
Clones or opens a local repository using GitPython.
"""
import logging
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Max file size to read (bytes) — skip binary / huge files
MAX_FILE_SIZE = 500_000


def clone_repository(url: str, name: Optional[str] = None) -> Path:
    """
    Clone a remote repository into data/repositories/<name>.
    Returns the local path.
    """
    from git import Repo, GitCommandError

    if name is None:
        # Derive name from URL
        name = url.rstrip("/").split("/")[-1].replace(".git", "")

    dest = settings.repos_dir / name
    if dest.exists():
        logger.info("Repository already exists at %s — pulling latest.", dest)
        try:
            repo = Repo(dest)
            repo.remotes.origin.pull()
        except Exception as e:
            logger.warning("Pull failed: %s — using existing clone.", e)
        return dest

    logger.info("Cloning %s into %s", url, dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        Repo.clone_from(url, dest)
        logger.info("Clone complete.")
    except GitCommandError as e:
        logger.error("Clone failed: %s", e)
        raise

    return dest


def get_local_repo(path: str) -> Path:
    """
    Use an existing local repository path.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Repository path does not exist: {path}")
    return p


def scan_files(repo_path: Path) -> list:
    """
    Walk the repository and return a list of dicts with file metadata.
    Skips binaries, .git directory, and huge files.
    """
    SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", "dist", "build"}
    SKIP_EXTS = {
        ".pyc", ".pyo", ".so", ".dll", ".exe", ".bin", ".jpg", ".jpeg",
        ".png", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz", ".lock",
        ".min.js", ".min.css",
    }

    files = []
    for p in repo_path.rglob("*"):
        if p.is_dir():
            continue
        # Skip hidden dirs and build dirs
        parts = set(p.relative_to(repo_path).parts)
        if parts & SKIP_DIRS:
            continue
        # Skip by extension
        if p.suffix.lower() in SKIP_EXTS:
            continue
        # Skip large files
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size > MAX_FILE_SIZE:
            continue
        # Try reading as text
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        rel_path = str(p.relative_to(repo_path)).replace("\\", "/")
        lang = _detect_language(p)
        files.append({
            "path": rel_path,
            "full_path": str(p),
            "language": lang,
            "size": size,
            "content": content,
        })

    return files


def _detect_language(path: Path) -> str:
    EXT_MAP = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".php": "php",
        ".cs": "csharp",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".toml": "toml",
        ".md": "markdown",
        ".txt": "text",
        ".sh": "shell",
        ".dockerfile": "docker",
        ".env": "env",
        ".sql": "sql",
        ".html": "html",
        ".css": "css",
    }
    name = path.name.lower()
    if name == "dockerfile":
        return "docker"
    if name in ("makefile", ".makefile"):
        return "makefile"
    return EXT_MAP.get(path.suffix.lower(), "unknown")
