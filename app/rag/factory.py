from pathlib import Path

from app.rag.chroma_vector_store import ChromaVectorStore
from app.rag.document_loader import DocumentLoader
from app.rag.embedding import EmbeddingClient
from app.rag.embedding_factory import create_embedding_client
from app.rag.hybrid_retriever import HybridKnowledgeRetriever


def create_retriever(
    knowledge_dir: Path = Path("data/knowledge_base"),
    embedding_client: EmbeddingClient | None = None,
    persist_directory: Path | None = None,
) -> HybridKnowledgeRetriever:
    client = embedding_client or create_embedding_client()
    vector_store = ChromaVectorStore(
        embedding_client=client,
        persist_directory=persist_directory or Path("data/chroma_db"),
    )
    document_loader = DocumentLoader(knowledge_dir=knowledge_dir)

    return HybridKnowledgeRetriever(
        document_loader=document_loader,
        vector_store=vector_store,
    )
