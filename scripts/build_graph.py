"""
Build Neo4j graph for an already-cloned repository.
Useful if you want to re-index the graph without re-cloning.

Usage:
    python scripts/build_graph.py --name my-repo
    python scripts/build_graph.py --path /path/to/repo
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")


def main():
    parser = argparse.ArgumentParser(description="Build the Neo4j graph for a repository")
    parser.add_argument("--name", help="Repository name (in data/repositories/)")
    parser.add_argument("--path", help="Direct path to repository")
    args = parser.parse_args()

    from pathlib import Path
    from app.config import settings
    from app.knowledge.neo4j_client import get_neo4j_client
    from app.ingestion.repository_loader import scan_files
    from app.ingestion.code_parser import parse_file
    from app.ingestion.dependency_parser import parse_dependencies
    from app.ingestion.git_parser import parse_git_history
    from app.ingestion.adr_parser import find_adrs

    if args.path:
        repo_path = Path(args.path)
        name = args.name or repo_path.name
    elif args.name:
        repo_path = settings.repos_dir / args.name
        name = args.name
    else:
        parser.print_help()
        sys.exit(1)

    if not repo_path.exists():
        print(f"  ✗  Path not found: {repo_path}")
        sys.exit(1)

    db = get_neo4j_client()
    if not db.is_connected():
        print("  ✗  Neo4j not connected. Check .env")
        sys.exit(1)

    print(f"\n  Building Neo4j graph for: {name}")

    db.create_repository(name)
    files = scan_files(repo_path)
    print(f"  Files: {len(files)}")

    for f in files:
        db.create_file(name, f["path"], f["language"])
        parsed = parse_file(f)
        for cls in parsed.get("classes", []):
            db.create_class(name, f["path"], cls["name"])
        for fn in parsed.get("functions", []):
            db.create_function(name, f["path"], fn["name"], fn.get("lineno", 0))
        for imp in parsed.get("imports", []):
            db.create_import(name, f["path"], imp.get("module", ""))

    deps = parse_dependencies(repo_path)
    for lang_deps in deps.values():
        if isinstance(lang_deps, list):
            for dep in lang_deps:
                if isinstance(dep, dict) and dep.get("name"):
                    db.create_dependency(name, dep["name"], dep.get("version", ""))

    commits = parse_git_history(repo_path)
    for c in commits:
        db.create_commit(name, c["hash"], c["message"][:500], c["author"], c["date"])

    adrs = find_adrs(repo_path)
    for adr in adrs:
        db.create_adr(name, adr["id"], adr["title"], adr.get("content", "")[:1000])

    summary = db.get_repository_summary(name)
    print("\n  ── Graph Summary ────────────────────────────")
    for k, v in summary.items():
        print(f"    {k:<12}: {v}")
    print(f"\n  ✓  Graph built for {name}")


if __name__ == "__main__":
    main()
