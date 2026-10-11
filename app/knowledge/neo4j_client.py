"""
Neo4j Client
Structural knowledge — what is connected to what.
"""
import logging
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Wrapper around the Neo4j driver with ARCHON-specific helpers."""

    def __init__(self):
        self.driver = None
        self._connected = False
        self._connect()

    def _connect(self):
        if settings.neo4j_password.startswith("PLACEHOLDER"):
            logger.warning("Neo4j credentials not configured — running in mock mode.")
            return

        try:
            from neo4j import GraphDatabase
            self.driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_username, settings.neo4j_password),
            )
            self._connected = True
            logger.info("Neo4j connected: %s", settings.neo4j_uri)
        except Exception as e:
            logger.error("Neo4j connection failed: %s", e)
            self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def verify(self) -> bool:
        if not self._connected:
            return False
        try:
            with self.driver.session(database=settings.neo4j_database) as session:
                result = session.run("RETURN 1 AS result")
                return result.single()["result"] == 1
        except Exception as e:
            logger.error("Neo4j verify failed: %s", e)
            return False

    def run(self, query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Run a Cypher query and return list of record dicts with serializable values."""
        if not self._connected:
            logger.warning("Neo4j not connected — returning empty results.")
            return []
        try:
            with self.driver.session(database=settings.neo4j_database) as session:
                result = session.run(query, params or {})
                return [_serialize_record(dict(record)) for record in result]
        except Exception as e:
            logger.error("Neo4j query failed: %s\nQuery: %s", e, query)
            return []

    def close(self):
        if self.driver:
            self.driver.close()

    # ─── Repository graph operations ────────────────────────────────────────

    def create_repository(self, name: str, url: str = "") -> bool:
        self.run(
            "MERGE (r:Repository {name: $name}) SET r.url = $url",
            {"name": name, "url": url},
        )
        return True

    def create_file(self, repo_name: str, file_path: str, language: str = "") -> bool:
        self.run(
            """
            MERGE (r:Repository {name: $repo})
            MERGE (f:File {path: $path, repository: $repo})
            SET f.language = $language
            MERGE (r)-[:CONTAINS]->(f)
            """,
            {"repo": repo_name, "path": file_path, "language": language},
        )
        return True

    def create_function(
        self, repo_name: str, file_path: str, func_name: str, lineno: int = 0
    ) -> bool:
        self.run(
            """
            MERGE (f:File {path: $path, repository: $repo})
            MERGE (fn:Function {name: $func, file: $path, repository: $repo})
            SET fn.lineno = $lineno
            MERGE (f)-[:DEFINES]->(fn)
            """,
            {"repo": repo_name, "path": file_path, "func": func_name, "lineno": lineno},
        )
        return True

    def create_class(self, repo_name: str, file_path: str, class_name: str) -> bool:
        self.run(
            """
            MERGE (f:File {path: $path, repository: $repo})
            MERGE (c:Class {name: $cls, file: $path, repository: $repo})
            MERGE (f)-[:DEFINES]->(c)
            """,
            {"repo": repo_name, "path": file_path, "cls": class_name},
        )
        return True

    def create_import(self, repo_name: str, from_file: str, to_module: str) -> bool:
        self.run(
            """
            MERGE (f:File {path: $from_file, repository: $repo})
            MERGE (m:Module {name: $module, repository: $repo})
            MERGE (f)-[:IMPORTS]->(m)
            """,
            {"repo": repo_name, "from_file": from_file, "module": to_module},
        )
        return True

    def create_dependency(self, repo_name: str, package: str, version: str = "") -> bool:
        self.run(
            """
            MERGE (r:Repository {name: $repo})
            MERGE (d:Dependency {name: $package, repository: $repo})
            SET d.version = $version
            MERGE (r)-[:DEPENDS_ON]->(d)
            """,
            {"repo": repo_name, "package": package, "version": version},
        )
        return True

    def create_service(self, repo_name: str, service_name: str, service_type: str = "") -> bool:
        self.run(
            """
            MERGE (r:Repository {name: $repo})
            MERGE (s:Service {name: $service, repository: $repo})
            SET s.type = $type
            MERGE (r)-[:CONTAINS]->(s)
            """,
            {"repo": repo_name, "service": service_name, "type": service_type},
        )
        return True

    def create_adr(self, repo_name: str, adr_id: str, title: str, content: str) -> bool:
        self.run(
            """
            MERGE (r:Repository {name: $repo})
            MERGE (a:ADR {id: $id, repository: $repo})
            SET a.title = $title, a.content = $content
            MERGE (r)-[:DOCUMENTED_BY]->(a)
            """,
            {"repo": repo_name, "id": adr_id, "title": title, "content": content},
        )
        return True

    def create_commit(
        self, repo_name: str, commit_hash: str, message: str, author: str, date: str
    ) -> bool:
        self.run(
            """
            MERGE (r:Repository {name: $repo})
            MERGE (c:Commit {hash: $hash, repository: $repo})
            SET c.message = $message, c.author = $author, c.date = $date
            MERGE (r)-[:CHANGED_BY]->(c)
            """,
            {
                "repo": repo_name,
                "hash": commit_hash,
                "message": message,
                "author": author,
                "date": date,
            },
        )
        return True

    def find_dependencies_of(self, component_name: str, repo_name: str, depth: int = 4) -> List[Dict]:
        """Find all components that depend on a given component (impact tracing)."""
        return self.run(
            f"""
            MATCH path = (n)-[:DEPENDS_ON|CALLS|USES|IMPORTS*1..{depth}]-(target)
            WHERE (target.name = $name OR target.path CONTAINS $name)
              AND (n.repository = $repo OR target.repository = $repo)
            RETURN path, n.name AS dependant, target.name AS dependency
            LIMIT 50
            """,
            {"name": component_name, "repo": repo_name},
        )

    def get_repository_summary(self, repo_name: str) -> Dict[str, Any]:
        """Return counts of all node types for a repository."""
        counts = {}
        for label in ["File", "Function", "Class", "Service", "Dependency", "ADR", "Commit"]:
            result = self.run(
                f"MATCH (n:{label} {{repository: $repo}}) RETURN count(n) AS cnt",
                {"repo": repo_name},
            )
            counts[label.lower()] = result[0]["cnt"] if result else 0
        return counts

    def get_all_dependencies(self, repo_name: str) -> List[Dict]:
        return self.run(
            "MATCH (r:Repository {name: $repo})-[:DEPENDS_ON]->(d:Dependency) RETURN d",
            {"repo": repo_name},
        )

    def get_files_by_language(self, repo_name: str, language: str) -> List[Dict]:
        return self.run(
            "MATCH (f:File {repository: $repo, language: $lang}) RETURN f",
            {"repo": repo_name, "lang": language},
        )


def _serialize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a Neo4j record dict into plain Python types (no Node/Relationship objects).
    Neo4j Node objects expose their properties via dict(node) or node.items().
    """
    out = {}
    for key, value in record.items():
        out[key] = _serialize_value(value)
    return out


def _serialize_value(value: Any) -> Any:
    """Recursively convert Neo4j graph types to plain dicts/lists."""
    # Neo4j Node or Relationship — extract properties
    try:
        from neo4j.graph import Node, Relationship, Path
        if isinstance(value, Node):
            return dict(value)
        if isinstance(value, Relationship):
            return {"type": value.type, **dict(value)}
        if isinstance(value, Path):
            return {
                "nodes": [dict(n) for n in value.nodes],
                "relationships": [{"type": r.type, **dict(r)} for r in value.relationships],
            }
    except ImportError:
        pass
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_value(v) for v in value]
    return value


_neo4j_instance: Optional[Neo4jClient] = None


def get_neo4j_client() -> Neo4jClient:
    global _neo4j_instance
    if _neo4j_instance is None:
        _neo4j_instance = Neo4jClient()
    return _neo4j_instance
