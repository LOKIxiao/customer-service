from app.rag.chroma_vector_store import ChromaVectorStore
from app.rag.document_loader import DocumentLoader
from app.rag.embedding import FakeEmbeddingClient
from app.rag.hybrid_retriever import HybridKnowledgeRetriever


def _make_retriever(kb_dir, persist_directory):
    return HybridKnowledgeRetriever(
        document_loader=DocumentLoader(knowledge_dir=kb_dir),
        vector_store=ChromaVectorStore(FakeEmbeddingClient(), persist_directory=persist_directory),
    )


def test_hybrid_retriever_retrieves_relevant_chunk(tmp_path):
    kb_dir = tmp_path / "knowledge_base"
    kb_dir.mkdir()
    (kb_dir / "refund_policy.md").write_text(
        "# 退款政策\n\n退款会在 1-3 个工作日内原路退回。",
        encoding="utf-8",
    )
    (kb_dir / "invoice.md").write_text(
        "# 发票\n\n电子发票在订单完成后自动开具。",
        encoding="utf-8",
    )

    retriever = _make_retriever(kb_dir, tmp_path / "chroma")

    results = retriever.retrieve("退款多久到账？", top_k=1)

    assert results
    assert results[0].source == "refund_policy.md"


def test_hybrid_retriever_respects_top_k(tmp_path):
    kb_dir = tmp_path / "knowledge_base"
    kb_dir.mkdir()
    (kb_dir / "a.md").write_text("# A\n\n退款政策第一条内容。", encoding="utf-8")
    (kb_dir / "b.md").write_text("# B\n\n退款政策第二条内容。", encoding="utf-8")
    (kb_dir / "c.md").write_text("# C\n\n退款政策第三条内容。", encoding="utf-8")

    retriever = _make_retriever(kb_dir, tmp_path / "chroma")

    results = retriever.retrieve("退款", top_k=2)

    assert len(results) <= 2


def test_hybrid_retriever_returns_empty_for_empty_knowledge_base(tmp_path):
    kb_dir = tmp_path / "knowledge_base"
    kb_dir.mkdir()

    retriever = _make_retriever(kb_dir, tmp_path / "chroma")

    assert retriever.retrieve("随便问点什么") == []


def test_hybrid_retriever_lazy_loads_only_once(tmp_path):
    kb_dir = tmp_path / "knowledge_base"
    kb_dir.mkdir()
    (kb_dir / "refund_policy.md").write_text(
        "# 退款政策\n\n退款会在 1-3 个工作日内原路退回。",
        encoding="utf-8",
    )

    retriever = _make_retriever(kb_dir, tmp_path / "chroma")

    first = retriever.retrieve("怎么退款")
    second = retriever.retrieve("怎么退款")

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
