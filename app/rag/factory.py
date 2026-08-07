import os
from pathlib import Path

from dotenv import load_dotenv

from app.rag.chroma_vector_store import ChromaVectorStore
from app.rag.document_loader import DocumentLoader
from app.rag.embedding import EmbeddingClient, FakeEmbeddingClient
from app.rag.embedding_factory import create_embedding_client
from app.rag.evidence_gate import EvidenceGate
from app.rag.hybrid_retriever import HybridKnowledgeRetriever
from app.rag.reranker import QwenReranker


def create_reranker() -> QwenReranker | None:
    load_dotenv()
    enabled = os.getenv("RERANK_ENABLED", "false").lower() == "true"
    if not enabled:
        return None

    return QwenReranker(
        api_key=os.getenv("RERANK_API_KEY") or os.getenv("LLM_API_KEY", ""),
        endpoint=os.getenv("RERANK_BASE_URL", ""),
        model=os.getenv("RERANK_MODEL", "qwen3-rerank"),
        instruction=os.getenv(
            "RERANK_INSTRUCTION",
            "Given a customer-service question, rank passages by whether they directly answer it.",
        ),
        timeout_seconds=float(os.getenv("RERANK_TIMEOUT_SECONDS", "30")),
    )


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
    gate_enabled = os.getenv("RAG_EVIDENCE_GATE_ENABLED", "true").lower() == "true"
    # Fake embedding 表示调用方明确要求离线/确定性执行，此时不能再因 .env
    # 的生产开关意外调用外部 rerank API。
    reranker = None if isinstance(client, FakeEmbeddingClient) else create_reranker()
    rerank_candidate_k = int(os.getenv("RERANK_CANDIDATE_K", "20"))

    return HybridKnowledgeRetriever(
        document_loader=document_loader,
        vector_store=vector_store,
        evidence_gate=(
            EvidenceGate(
                vector_threshold=float(os.getenv("RAG_VECTOR_THRESHOLD", "0.75")),
                lexical_coverage_threshold=float(os.getenv("RAG_LEXICAL_COVERAGE_THRESHOLD", "0.3")),
                bm25_threshold=float(os.getenv("RAG_BM25_THRESHOLD", "9.0")),
                lexical_bm25_threshold=float(os.getenv("RAG_LEXICAL_BM25_THRESHOLD", "0.1")),
                strong_bm25_threshold=float(os.getenv("RAG_STRONG_BM25_THRESHOLD", "12.0")),
            )
            if gate_enabled
            else None
        ),
        reranker=reranker,
        candidate_k=max(10, rerank_candidate_k) if reranker else 10,
        rerank_candidate_k=rerank_candidate_k,
    )
