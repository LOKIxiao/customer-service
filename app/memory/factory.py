from pathlib import Path

from app.memory.long_term_store import UserMemoryStore
from app.rag.embedding import EmbeddingClient
from app.rag.embedding_factory import create_embedding_client


def create_memory_store(
    embedding_client: EmbeddingClient | None = None,
    persist_directory: Path | None = None,
) -> UserMemoryStore:
    client = embedding_client or create_embedding_client()

    return UserMemoryStore(
        embedding_client=client,
        persist_directory=persist_directory or Path("data/user_memory_db"),
    )
