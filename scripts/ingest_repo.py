"""
Ingest a repository into ARCHON's knowledge bases.

Usage:
    # From a remote URL
    python scripts/ingest_repo.py https://github.com/example/repo.git

    # From a local path
    python scripts/ingest_repo.py --local /path/to/repo

    # With a custom name
    python scripts/ingest_repo.py https://github.com/example/repo.git --name my-repo
"""
import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Ingest a repository into ARCHON")
    parser.add_argument("source", nargs="?", help="Remote git URL")
    parser.add_argument("--local", help="Local repository path")
    parser.add_argument("--name", help="Override repository name")
    args = parser.parse_args()

    if not args.source and not args.local:
        parser.print_help()
        sys.exit(1)

    from app.ingestion.repository_loader import clone_repository, get_local_repo
    from app.ingestion.indexer import ingest_repository

    # Progress callback
    def progress(msg: str, pct: int):
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        print(f"\r  [{bar}] {pct:3d}%  {msg:<40}", end="", flush=True)
        if pct == 100:
            print()

    # Resolve repository path
    if args.local:
        repo_path = get_local_repo(args.local)
        name = args.name or repo_path.name
    else:
        url = args.source
        name = args.name or url.rstrip("/").split("/")[-1].replace(".git", "")
        print(f"\n  Cloning {url} ...")
        repo_path = clone_repository(url, name)

    print(f"\n  Repository : {name}")
    print(f"  Path       : {repo_path}")
    print()

    summary = ingest_repository(repo_path, name, progress_callback=progress)

    print("\n  ── Ingestion Summary ─────────────────────────────")
    for key, val in summary.items():
        if key != "errors":
            print(f"    {key:<18}: {val}")

    if summary.get("errors"):
        print(f"\n  ⚠  {len(summary['errors'])} warnings:")
        for err in summary["errors"][:5]:
            print(f"    - {err}")

    print(f"\n  ✓  {name} is ready for analysis.")


if __name__ == "__main__":
    main()
