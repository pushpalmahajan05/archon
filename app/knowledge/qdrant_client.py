"""
Qdrant Client
Semantic knowledge — what evidence is semantically relevant.
"""
import logging
import uuid
from typing import Any, Dict, List, Optional

from app.config import settings
from app.llm.embeddings import embed_text, embed_texts

logger = logging.getLogger(__name__)

VECTOR_DIM = 384  # all-MiniLM-L6-v2 dimension


class QdrantClientWrapper:
    """Wrapper around the Qdrant client with ARCHON-specific helpers."""

    def __init__(self):
        self.client = None
        self._connected = False
        self._connect()

    def _connect(self):
        if settings.qdrant_api_key.startswith("PLACEHOLDER"):
            logger.warning("Qdrant credentials not configured — running in mock mode.")
            self._store: List[Dict] = []  # in-memory fallback
            return

        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            self.client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key,
            )
            # Ensure collection exists
            self._ensure_collection()
            self._connected = True
            logger.info("Qdrant connected: %s", settings.qdrant_url)
        except Exception as e:
            logger.error("Qdrant connection failed: %s", e)
            self._store = []

    def _ensure_collection(self):
        from qdrant_client.models import Distance, VectorParams, PayloadSchemaType

        existing = [c.name for c in self.client.get_collections().collections]
        if settings.qdrant_collection not in existing:
            self.client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
            )
            logger.info("Created Qdrant collection: %s", settings.qdrant_collection)

        # Create payload indexes required for filtered search and deletion
        self._ensure_payload_index("repository", "keyword")
        self._ensure_payload_index("type", "keyword")
        self._ensure_payload_index("file", "keyword")

    def _ensure_payload_index(self, field: str, field_type: str):
        """Create a payload index if it doesn't already exist."""
        try:
            from qdrant_client.models import PayloadSchemaType
            schema = PayloadSchemaType.KEYWORD if field_type == "keyword" else PayloadSchemaType.INTEGER
            self.client.create_payload_index(
                collection_name=settings.qdrant_collection,
                field_name=field,
                field_schema=schema,
            )
            logger.info("Payload index ensured: %s", field)
        except Exception as e:
            # Index may already exist — that's fine
            logger.debug("Payload index %s: %s", field, e)

    def is_connected(self) -> bool:
        return self._connected

    def upsert(self, chunks: List[Dict[str, Any]]) -> int:
        """
        Upsert evidence chunks.
        Each chunk: {"text": str, "repository": str, "file": str, "type": str, ...}
        Returns number of chunks indexed.
        """
        if not chunks:
            return 0

        if not self._connected:
            # In-memory fallback
            for chunk in chunks:
                chunk["_id"] = str(uuid.uuid4())
                self._store.append(chunk)
            return len(chunks)

        from qdrant_client.models import PointStruct

        texts = [c["text"] for c in chunks]
        vectors = embed_texts(texts)

        points = []
        for chunk, vec in zip(chunks, vectors):
            point_id = str(uuid.uuid4())
            payload = {k: v for k, v in chunk.items() if k != "text"}
            payload["text"] = chunk["text"][:2000]  # Qdrant payload limit guard
            points.append(PointStruct(id=point_id, vector=vec, payload=payload))

        self.client.upsert(
            collection_name=settings.qdrant_collection,
            points=points,
        )
        return len(points)

    def search(
        self,
        query: str,
        repository: Optional[str] = None,
        evidence_type: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Semantic search for relevant evidence chunks."""
        query_vec = embed_text(query)

        if not self._connected:
            return self._mock_search(query, repository, evidence_type, top_k)

        from qdrant_client.models import Filter, FieldCondition, MatchValue

        filters = []
        if repository:
            filters.append(FieldCondition(key="repository", match=MatchValue(value=repository)))
        if evidence_type:
            filters.append(FieldCondition(key="type", match=MatchValue(value=evidence_type)))

        search_filter = None
        if filters:
            from qdrant_client.models import Filter as QFilter
            search_filter = QFilter(must=filters)

        # qdrant-client >= 1.7 uses query_points; older versions use search
        try:
            from qdrant_client.models import Query
            response = self.client.query_points(
                collection_name=settings.qdrant_collection,
                query=query_vec,
                query_filter=search_filter,
                limit=top_k,
            )
            hits = response.points
        except AttributeError:
            # Fallback for older client versions
            hits = self.client.search(
                collection_name=settings.qdrant_collection,
                query_vector=query_vec,
                query_filter=search_filter,
                limit=top_k,
            )

        return [
            {
                "score": hit.score,
                "text": hit.payload.get("text", ""),
                **hit.payload,
            }
            for hit in hits
        ]

    def _mock_search(
        self, query: str, repository: Optional[str], evidence_type: Optional[str], top_k: int
    ) -> List[Dict[str, Any]]:
        """Simple keyword search over in-memory store."""
        query_lower = query.lower()
        results = []
        for item in self._store:
            text = item.get("text", "").lower()
            repo_match = repository is None or item.get("repository") == repository
            type_match = evidence_type is None or item.get("type") == evidence_type
            if repo_match and type_match and any(w in text for w in query_lower.split()):
                results.append({"score": 0.5, **item})
        return results[:top_k]

    def delete_by_repository(self, repository: str) -> bool:
        """Remove all chunks for a repository (used when re-indexing)."""
        if not self._connected:
            self._store = [c for c in self._store if c.get("repository") != repository]
            return True

        from qdrant_client.models import Filter, FieldCondition, MatchValue
        self.client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=Filter(
                must=[FieldCondition(key="repository", match=MatchValue(value=repository))]
            ),
        )
        return True

    def delete_by_file(self, repository: str, file_path: str) -> bool:
        """Remove all chunks for a specific file (used during incremental update)."""
        if not self._connected:
            self._store = [
                c for c in self._store
                if not (c.get("repository") == repository and c.get("file") == file_path)
            ]
            return True

        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            self.client.delete(
                collection_name=settings.qdrant_collection,
                points_selector=Filter(
                    must=[
                        FieldCondition(key="repository", match=MatchValue(value=repository)),
                        FieldCondition(key="file", match=MatchValue(value=file_path)),
                    ]
                ),
            )
        except Exception as e:
            logger.debug("delete_by_file %s/%s: %s", repository, file_path, e)
        return True

    def count(self, repository: Optional[str] = None) -> int:
        if not self._connected:
            if repository:
                return sum(1 for c in self._store if c.get("repository") == repository)
            return len(self._store)
        result = self.client.count(collection_name=settings.qdrant_collection)
        return result.count


_qdrant_instance: Optional[QdrantClientWrapper] = None


def get_qdrant_client() -> QdrantClientWrapper:
    global _qdrant_instance
    if _qdrant_instance is None:
        _qdrant_instance = QdrantClientWrapper()
    return _qdrant_instance
