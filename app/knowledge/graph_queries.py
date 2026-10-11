"""
ARCHON Graph Query Helpers
Higher-level Neo4j queries for agent consumption.
"""
from typing import Any, Dict, List

from app.knowledge.neo4j_client import get_neo4j_client


def get_impact_graph(component_name: str, repo_name: str, depth: int = 4) -> List[Dict]:
    """
    Trace all components that use/depend on a given component.
    Used by the Change Impact Agent.
    """
    db = get_neo4j_client()
    return db.find_dependencies_of(component_name, repo_name, depth)


def get_architecture_graph(repo_name: str) -> Dict[str, Any]:
    """
    Fetch the full architectural picture for a repository.
    """
    db = get_neo4j_client()
    files = db.run(
        "MATCH (f:File {repository: $repo}) RETURN f LIMIT 200",
        {"repo": repo_name},
    )
    services = db.run(
        "MATCH (s:Service {repository: $repo}) RETURN s",
        {"repo": repo_name},
    )
    deps = db.run(
        "MATCH (r:Repository {name: $repo})-[:DEPENDS_ON]->(d) RETURN d",
        {"repo": repo_name},
    )
    relationships = db.run(
        """
        MATCH (a {repository: $repo})-[r]->(b {repository: $repo})
        RETURN type(r) AS rel, a.name AS from_node, b.name AS to_node
        LIMIT 200
        """,
        {"repo": repo_name},
    )
    return {
        "files": files,
        "services": services,
        "dependencies": deps,
        "relationships": relationships,
    }


def get_history_graph(repo_name: str, keyword: str = "") -> Dict[str, Any]:
    """
    Fetch ADRs and commits relevant to a keyword.
    Used by the Decision Historian Agent.
    """
    db = get_neo4j_client()
    if keyword:
        adrs = db.run(
            """
            MATCH (a:ADR {repository: $repo})
            WHERE toLower(a.content) CONTAINS toLower($kw)
               OR toLower(a.title) CONTAINS toLower($kw)
            RETURN a LIMIT 20
            """,
            {"repo": repo_name, "kw": keyword},
        )
        commits = db.run(
            """
            MATCH (c:Commit {repository: $repo})
            WHERE toLower(c.message) CONTAINS toLower($kw)
            RETURN c LIMIT 30
            """,
            {"repo": repo_name, "kw": keyword},
        )
    else:
        adrs = db.run(
            "MATCH (a:ADR {repository: $repo}) RETURN a LIMIT 20",
            {"repo": repo_name},
        )
        commits = db.run(
            "MATCH (c:Commit {repository: $repo}) RETURN c ORDER BY c.date DESC LIMIT 30",
            {"repo": repo_name},
        )
    return {"adrs": adrs, "commits": commits}


def get_repo_summary_text(repo_name: str) -> str:
    """Format a repository summary as readable text for agent prompts."""
    db = get_neo4j_client()
    summary = db.get_repository_summary(repo_name)
    deps = db.get_all_dependencies(repo_name)
    dep_names = [d.get("d", {}).get("name", str(d)) for d in deps]

    lines = [
        f"Repository: {repo_name}",
        f"Files: {summary.get('file', 0)}",
        f"Functions: {summary.get('function', 0)}",
        f"Classes: {summary.get('class', 0)}",
        f"Services: {summary.get('service', 0)}",
        f"ADRs: {summary.get('adr', 0)}",
        f"Commits indexed: {summary.get('commit', 0)}",
        f"Dependencies: {', '.join(dep_names) if dep_names else 'none'}",
    ]
    return "\n".join(lines)
