"""
Test all external service connections.
Run before anything else to verify your .env is correct.

Usage:
    python scripts/test_connections.py
"""
import sys
import os

# Allow imports from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings


def test_groq():
    print("\n── Groq LLM ─────────────────────────────────────")
    if settings.groq_api_key.startswith("PLACEHOLDER"):
        print("  ⚠  GROQ_API_KEY not configured (placeholder). Skipping live test.")
        return False

    try:
        from app.llm.groq_client import ask_groq
        result = ask_groq(
            "You are a helpful assistant.",
            "Say exactly: ARCHON connection successful",
        )
        print(f"  ✓  Response: {result.strip()[:80]}")
        return True
    except Exception as e:
        print(f"  ✗  Failed: {e}")
        return False


def test_neo4j():
    print("\n── Neo4j ────────────────────────────────────────")
    if settings.neo4j_password.startswith("PLACEHOLDER"):
        print("  ⚠  NEO4J_PASSWORD not configured (placeholder). Skipping live test.")
        return False

    try:
        from app.knowledge.neo4j_client import Neo4jClient
        db = Neo4jClient()
        ok = db.verify()
        db.close()
        if ok:
            print("  ✓  Neo4j connected and verified.")
        else:
            print("  ✗  Neo4j verify() returned False.")
        return ok
    except Exception as e:
        print(f"  ✗  Failed: {e}")
        return False


def test_qdrant():
    print("\n── Qdrant ───────────────────────────────────────")
    if settings.qdrant_api_key.startswith("PLACEHOLDER"):
        print("  ⚠  QDRANT_API_KEY not configured (placeholder). Running in mock mode.")
        # Mock mode still works — test it
        from app.knowledge.qdrant_client import QdrantClientWrapper
        q = QdrantClientWrapper()
        q.upsert([{"text": "test chunk", "repository": "test", "type": "code"}])
        results = q.search("test", repository="test")
        print(f"  ✓  Mock mode OK. Returned {len(results)} results.")
        return True

    try:
        from app.knowledge.qdrant_client import QdrantClientWrapper
        q = QdrantClientWrapper()
        count = q.count()
        print(f"  ✓  Qdrant connected. Collection has {count} vectors.")
        return True
    except Exception as e:
        print(f"  ✗  Failed: {e}")
        return False


def test_embeddings():
    print("\n── Embeddings ───────────────────────────────────")
    try:
        from app.llm.embeddings import embed_text
        vec = embed_text("test sentence for embedding")
        print(f"  ✓  Embeddings OK. Vector dim={len(vec)}")
        return True
    except Exception as e:
        print(f"  ✗  Failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 52)
    print("  ARCHON Connection Tests")
    print("=" * 52)

    results = {
        "Groq": test_groq(),
        "Neo4j": test_neo4j(),
        "Qdrant": test_qdrant(),
        "Embeddings": test_embeddings(),
    }

    print("\n── Summary ──────────────────────────────────────")
    all_ok = True
    for name, ok in results.items():
        status = "✓" if ok else ("⚠ (placeholder)" if ok is False else "✗")
        print(f"  {status}  {name}")
        if ok is False and name in ("Groq", "Neo4j"):
            all_ok = False

    print()
    if all_ok:
        print("  All critical services ready.")
    else:
        print("  Some services need configuration. Check .env")
    print("=" * 52)
