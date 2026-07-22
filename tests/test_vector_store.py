from app.rag.embedding import FakeEmbeddingClient
from app.rag.vector_store import InMemoryVectorStore
from app.schemas.rag import DocumentChunk


def test_vector_store_retrieves_relevant_chunk():
    store = InMemoryVectorStore(FakeEmbeddingClient())

    store.add_chunks(
        [
            DocumentChunk(
                chunk_id="refund_policy.md:0",
                source="refund_policy.md",
                content="退款会在 1-3 个工作日内原路退回。",
            ),
            DocumentChunk(
                chunk_id="invoice.md:0",
                source="invoice.md",
                content="用户可以在订单详情页申请发票。",
            ),
        ]
    )

    results = store.search("退款多久到账？")

    assert results
    assert results[0].source == "refund_policy.md"