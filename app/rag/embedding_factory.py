import os

from dotenv import load_dotenv

from app.rag.embedding import EmbeddingClient, FakeEmbeddingClient, QwenEmbeddingClient


def create_embedding_client() -> EmbeddingClient:
    load_dotenv()

    enabled = os.getenv("EMBEDDING_ENABLED", "false").lower() == "true"
    if not enabled:
        return FakeEmbeddingClient()

    return QwenEmbeddingClient()