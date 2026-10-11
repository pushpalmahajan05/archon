"""
ARCHON Configuration
Loads settings from environment variables / .env file.
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    groq_api_key: str = "PLACEHOLDER_GROQ_API_KEY"
    groq_model: str = "llama-3.1-8b-instant"

    # Neo4j
    neo4j_uri: str = "neo4j+s://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "PLACEHOLDER_NEO4J_PASSWORD"
    neo4j_database: str = "neo4j"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = "PLACEHOLDER_QDRANT_API_KEY"
    qdrant_collection: str = "archon_evidence"

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    max_repo_size_mb: int = 500

    # Derived paths
    @property
    def data_dir(self) -> Path:
        return Path(__file__).parent.parent / "data"

    @property
    def repos_dir(self) -> Path:
        return self.data_dir / "repositories"

    @property
    def prompts_dir(self) -> Path:
        return Path(__file__).parent / "prompts"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
