from app.rag.document_loader import DocumentLoader
from app.rag.embedding import FakeEmbeddingClient
from app.rag.retriever import KnowledgeRetriever
from app.rag.vector_store import InMemoryVectorStore


def test_knowledge_retriever_loads_and_searches_documents(tmp_path):
    kb_dir = tmp_path / "knowledge_base"
    kb_dir.mkdir()

    (kb_dir / "refund_policy.md").write_text(
        "# 退款政策\n\n退款会在 1-3 个工作日内原路退回。",
        encoding="utf-8",
    )

    retriever = KnowledgeRetriever(
        document_loader=DocumentLoader(knowledge_dir=kb_dir),
        vector_store=InMemoryVectorStore(FakeEmbeddingClient()),
    )

    results = retriever.retrieve("退款多久到账？")

    assert results
    assert results[0].source == "refund_policy.md"