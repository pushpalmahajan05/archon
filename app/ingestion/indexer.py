"""
ARCHON Repository Indexer
Orchestrates the full ingestion pipeline with incremental update support.

On first run: full ingestion of all files.
On subsequent runs: only changed/new/deleted files are re-processed.
  - File changes detected via SHA-256 hash stored in a local manifest.
  - New commits since last run are appended.
  - Neo4j uses MERGE so unchanged nodes are never duplicated.
  - Qdrant chunks for changed files are deleted then re-uploaded.
"""
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from app.config import settings
from app.ingestion.repository_loader import scan_files
from app.ingestion.code_parser import parse_file, chunk_file_content
from app.ingestion.dependency_parser import parse_dependencies
from app.ingestion.git_parser import parse_git_history
from app.ingestion.adr_parser import find_adrs
from app.knowledge.neo4j_client import get_neo4j_client
from app.knowledge.qdrant_client import get_qdrant_client

logger = logging.getLogger(__name__)

# Manifest is stored alongside the repo in data/repositories/<name>/.archon_manifest.json
MANIFEST_FILE = ".archon_manifest.json"


# ── Manifest helpers ───────────────────────────────────────────────────────────

def _manifest_path(repo_path: Path) -> Path:
    return repo_path / MANIFEST_FILE


def _load_manifest(repo_path: Path) -> Dict[str, Any]:
    """Load the existing manifest or return a blank one."""
    p = _manifest_path(repo_path)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"file_hashes": {}, "last_commit": None, "indexed_adrs": []}


def _save_manifest(repo_path: Path, manifest: Dict[str, Any]):
    p = _manifest_path(repo_path)
    p.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _file_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _compute_hashes(files: List[Dict]) -> Dict[str, str]:
    return {f["path"]: _file_hash(f["content"]) for f in files}


def _diff_files(
    files: List[Dict],
    old_hashes: Dict[str, str],
) -> tuple[List[Dict], List[Dict], Set[str]]:
    """
    Compare current files against stored hashes.
    Returns:
        changed_or_new  — files that need re-indexing
        unchanged       — files to skip
        deleted_paths   — paths in old_hashes that no longer exist
    """
    current_paths = {f["path"] for f in files}
    old_paths = set(old_hashes.keys())

    deleted = old_paths - current_paths

    changed_or_new, unchanged = [], []
    for f in files:
        old_hash = old_hashes.get(f["path"])
        new_hash = _file_hash(f["content"])
        f["_hash"] = new_hash
        if old_hash != new_hash:
            changed_or_new.append(f)
        else:
            unchanged.append(f)

    return changed_or_new, unchanged, deleted


# ── Main entry point ───────────────────────────────────────────────────────────

def ingest_repository(
    repo_path: Path,
    repo_name: Optional[str] = None,
    progress_callback: Optional[Callable[[str, int], None]] = None,
    force_full: bool = False,
) -> Dict[str, Any]:
    """
    Ingest (or incrementally update) a repository.

    Args:
        repo_path:         Local path to the repository.
        repo_name:         Override for the repository name/slug.
        progress_callback: Optional fn(message, percent) for progress reporting.
        force_full:        If True, ignore the manifest and do a full re-index.

    Returns:
        Summary dict with counts of what was indexed/updated/skipped.
    """
    if repo_name is None:
        repo_name = repo_path.name

    def _log(msg: str, pct: int = 0):
        logger.info("[%s] %s (%d%%)", repo_name, msg, pct)
        if progress_callback:
            progress_callback(msg, pct)

    db = get_neo4j_client()
    qdrant = get_qdrant_client()

    # Load existing manifest
    manifest = _load_manifest(repo_path)
    is_first_run = not manifest["file_hashes"] or force_full

    if is_first_run:
        _log("Starting full ingestion", 0)
    else:
        _log("Starting incremental update", 0)

    summary = {
        "repository": repo_name,
        "mode": "full" if is_first_run else "incremental",
        "files_total": 0,
        "files_changed": 0,
        "files_skipped": 0,
        "files_deleted": 0,
        "functions": 0,
        "classes": 0,
        "imports": 0,
        "dependencies": 0,
        "commits_new": 0,
        "adrs": 0,
        "vectors_added": 0,
        "errors": [],
    }

    # ── Step 1: Repository node ──────────────────────────────────────────────
    db.create_repository(repo_name, url=str(repo_path))

    # ── Step 2: Scan all files ───────────────────────────────────────────────
    _log("Scanning files", 10)
    all_files = scan_files(repo_path)
    summary["files_total"] = len(all_files)

    # ── Step 3: Diff against manifest ────────────────────────────────────────
    if is_first_run:
        changed_files = all_files
        unchanged_files = []
        deleted_paths: Set[str] = set()
    else:
        changed_files, unchanged_files, deleted_paths = _diff_files(
            all_files, manifest["file_hashes"]
        )

    summary["files_changed"] = len(changed_files)
    summary["files_skipped"] = len(unchanged_files)
    summary["files_deleted"] = len(deleted_paths)

    _log(
        f"Files: {len(changed_files)} changed/new, "
        f"{len(unchanged_files)} unchanged, "
        f"{len(deleted_paths)} deleted",
        15,
    )

    # ── Step 4: Remove deleted files from graph ───────────────────────────────
    if deleted_paths:
        _log(f"Removing {len(deleted_paths)} deleted files from graph", 17)
        for path in deleted_paths:
            db.run(
                "MATCH (f:File {path: $path, repository: $repo}) DETACH DELETE f",
                {"path": path, "repo": repo_name},
            )
            # Remove old vectors for this file from Qdrant
            qdrant.delete_by_file(repo_name, path)

    # ── Step 5: Remove old vectors for changed files (before re-indexing) ────
    if changed_files and not is_first_run:
        _log("Removing stale vectors for changed files", 18)
        for f in changed_files:
            qdrant.delete_by_file(repo_name, f["path"])

    # ── Step 6: Parse and index changed/new files ─────────────────────────────
    _log("Parsing and indexing changed files", 20)
    all_chunks = []

    for f in changed_files:
        f["repository"] = repo_name
        try:
            db.create_file(repo_name, f["path"], f["language"])

            parsed = parse_file(f)
            for cls in parsed.get("classes", []):
                db.create_class(repo_name, f["path"], cls["name"])
                summary["classes"] += 1
            for fn in parsed.get("functions", []):
                db.create_function(repo_name, f["path"], fn["name"], fn.get("lineno", 0))
                summary["functions"] += 1
            for imp in parsed.get("imports", []):
                db.create_import(repo_name, f["path"], imp.get("module", ""))
                summary["imports"] += 1

            chunks = chunk_file_content(f)
            all_chunks.extend(chunks)

            # Markdown docs
            if f["language"] == "markdown":
                all_chunks.append({
                    "text": f["content"][:2000],
                    "repository": repo_name,
                    "file": f["path"],
                    "type": "readme" if "readme" in f["path"].lower() else "documentation",
                    "language": "markdown",
                    "line_start": 1,
                    "line_end": f["content"].count("\n"),
                })
        except Exception as e:
            err = f"Error processing {f['path']}: {e}"
            logger.warning(err)
            summary["errors"].append(err)

    # ── Step 7: Dependencies (always re-parse — manifests can change) ─────────
    _log("Parsing dependencies", 50)
    try:
        deps = parse_dependencies(repo_path)
        for lang_deps in deps.values():
            if isinstance(lang_deps, list):
                for dep in lang_deps:
                    if isinstance(dep, str):
                        db.create_dependency(repo_name, dep)
                    elif isinstance(dep, dict) and dep.get("name"):
                        db.create_dependency(repo_name, dep["name"], dep.get("version", ""))
                        summary["dependencies"] += 1
        for svc in deps.get("docker_services", []):
            db.create_service(repo_name, svc, "docker")
    except Exception as e:
        err = f"Dependency parsing error: {e}"
        logger.warning(err)
        summary["errors"].append(err)

    # ── Step 8: New commits only ──────────────────────────────────────────────
    _log("Indexing git history (new commits only)", 60)
    try:
        commits = parse_git_history(repo_path)
        last_known = manifest.get("last_commit")
        new_commits = []

        if last_known is None or is_first_run:
            new_commits = commits
        else:
            # Only commits we haven't seen yet
            for c in commits:
                if c["hash"] == last_known:
                    break
                new_commits.append(c)

        summary["commits_new"] = len(new_commits)
        for commit in new_commits:
            db.create_commit(
                repo_name,
                commit["hash"],
                commit["message"][:500],
                commit["author"],
                commit["date"],
            )
            all_chunks.append({
                "text": f"Commit {commit['hash']} by {commit['author']} on {commit['date']}: {commit['message'][:300]}",
                "repository": repo_name,
                "type": "commit",
                "commit_hash": commit["hash"],
                "author": commit["author"],
                "date": commit["date"],
            })

        # Store the most recent commit hash
        if commits:
            manifest["last_commit"] = commits[0]["hash"]

    except Exception as e:
        err = f"Git parsing error: {e}"
        logger.warning(err)
        summary["errors"].append(err)

    # ── Step 9: ADRs (only if new ones found) ────────────────────────────────
    _log("Indexing ADRs", 70)
    try:
        adrs = find_adrs(repo_path)
        indexed_adr_ids = set(manifest.get("indexed_adrs", []))
        new_adrs = [a for a in adrs if a["id"] not in indexed_adr_ids]

        summary["adrs"] = len(new_adrs)
        for adr in new_adrs:
            db.create_adr(repo_name, adr["id"], adr["title"], adr.get("content", "")[:1000])
            all_chunks.append({
                "text": f"ADR {adr['id']}: {adr['title']}\n{adr.get('content', '')[:1500]}",
                "repository": repo_name,
                "file": adr.get("file", ""),
                "type": "adr",
                "adr_id": adr["id"],
                "title": adr["title"],
            })
            indexed_adr_ids.add(adr["id"])

        manifest["indexed_adrs"] = list(indexed_adr_ids)
    except Exception as e:
        err = f"ADR parsing error: {e}"
        logger.warning(err)
        summary["errors"].append(err)

    # ── Step 10: Upload new/changed chunks to Qdrant ──────────────────────────
    if all_chunks:
        _log(f"Uploading {len(all_chunks)} chunks to Qdrant", 80)
        try:
            batch_size = 100
            total_uploaded = 0
            for i in range(0, len(all_chunks), batch_size):
                batch = all_chunks[i: i + batch_size]
                uploaded = qdrant.upsert(batch)
                total_uploaded += uploaded
            summary["vectors_added"] = total_uploaded
        except Exception as e:
            err = f"Qdrant upload error: {e}"
            logger.error(err)
            summary["errors"].append(err)
    else:
        _log("No new chunks to upload", 80)

    # ── Step 11: Save updated manifest ────────────────────────────────────────
    new_hashes = _compute_hashes(all_files)
    manifest["file_hashes"] = new_hashes
    _save_manifest(repo_path, manifest)

    _log("Ingestion complete", 100)
    logger.info("Ingestion summary: %s", summary)
    return summary
