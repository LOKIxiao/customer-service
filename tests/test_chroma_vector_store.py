from app.rag.chroma_vector_store import ChromaVectorStore
from app.rag.embedding import FakeEmbeddingClient
from app.schemas.rag import DocumentChunk


def _chunks():
    return [
        DocumentChunk(chunk_id="a:0", source="a.md", content="退款会在1到3个工作日内原路退回到账"),
        DocumentChunk(chunk_id="b:0", source="b.md", content="电子发票在订单完成后自动开具"),
    ]


def test_chroma_vector_store_retrieves_relevant_chunk(tmp_path):
    store = ChromaVectorStore(FakeEmbeddingClient(), persist_directory=tmp_path / "chroma")

    store.add_chunks(_chunks())
    results = store.search("退款多久到账", top_k=1)

    assert results
    assert results[0].source == "a.md"


def test_chroma_vector_store_empty_collection_returns_empty(tmp_path):
    store = ChromaVectorStore(FakeEmbeddingClient(), persist_directory=tmp_path / "chroma")

    assert store.search("随便问点什么") == []


def test_chroma_vector_store_rebuild_does_not_duplicate(tmp_path):
    persist_directory = tmp_path / "chroma"

    store = ChromaVectorStore(FakeEmbeddingClient(), persist_directory=persist_directory)
    store.add_chunks(_chunks())

    # 模拟第二次进程启动重新加载同一批 chunk：不应该出现重复计数
    store_reloaded = ChromaVectorStore(FakeEmbeddingClient(), persist_directory=persist_directory)
    store_reloaded.add_chunks(_chunks())

    assert store_reloaded._collection.count() == len(_chunks())
