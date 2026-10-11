"""
Build Qdrant vector index for an already-cloned repository.

Usage:
    python scripts/build_vectors.py --name my-repo
    python scripts/build_vectors.py --path /path/to/repo
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")


def main():
    parser = argparse.ArgumentParser(description="Build the Qdrant vector index for a repository")
    parser.add_argument("--name", help="Repository name (in data/repositories/)")
    parser.add_argument("--path", help="Direct path to repository")
    parser.add_argument("--clear", action="store_true", help="Clear existing vectors first")
    args = parser.parse_args()

    from pathlib import Path
    from app.config import settings
    from app.knowledge.qdrant_client import get_qdrant_client
    from app.ingestion.repository_loader import scan_files
    from app.ingestion.code_parser import chunk_file_content
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

    qdrant = get_qdrant_client()

    if args.clear:
        print(f"  Clearing existing vectors for {name}...")
        qdrant.delete_by_repository(name)

    print(f"\n  Building vector index for: {name}")

    files = scan_files(repo_path)
    all_chunks = []

    for f in files:
        f["repository"] = name
        chunks = chunk_file_content(f)
        all_chunks.extend(chunks)
        if f["language"] == "markdown":
            all_chunks.append({
                "text": f["content"][:2000],
                "repository": name,
                "file": f["path"],
                "type": "readme" if "readme" in f["path"].lower() else "documentation",
            })

    commits = parse_git_history(repo_path)
    for c in commits:
        all_chunks.append({
            "text": f"Commit {c['hash']} by {c['author']}: {c['message'][:300]}",
            "repository": name,
            "type": "commit",
            "commit_hash": c["hash"],
        })

    adrs = find_adrs(repo_path)
    for adr in adrs:
        all_chunks.append({
            "text": f"ADR {adr['id']}: {adr['title']}\n{adr.get('content', '')[:1500]}",
            "repository": name,
            "file": adr.get("file", ""),
            "type": "adr",
        })

    print(f"  Uploading {len(all_chunks)} chunks...")
    batch_size = 100
    total = 0
    for i in range(0, len(all_chunks), batch_size):
        n = qdrant.upsert(all_chunks[i: i + batch_size])
        total += n
        print(f"\r  Progress: {min(i + batch_size, len(all_chunks))}/{len(all_chunks)}", end="")
    print()

    print(f"\n  ✓  {total} vectors indexed for {name}")


if __name__ == "__main__":
    main()
