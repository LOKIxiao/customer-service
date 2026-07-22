from app.rag.bm25 import BM25Index
from app.schemas.rag import DocumentChunk


def _chunks():
    return [
        DocumentChunk(chunk_id="a:0", source="a.md", content="退款会在1到3个工作日内原路退回到账"),
        DocumentChunk(chunk_id="b:0", source="b.md", content="电子发票在订单完成后自动开具"),
        DocumentChunk(chunk_id="c:0", source="c.md", content="蓝牙耳机连接不上怎么办"),
    ]


def test_bm25_ranks_exact_keyword_match_first():
    index = BM25Index(_chunks())

    results = index.search("退款多久到账")

    assert results
    assert results[0][0].source == "a.md"


def test_bm25_returns_empty_for_unrelated_query():
    index = BM25Index(_chunks())

    assert index.search("完全无关的随便query内容xyz") == []


def test_bm25_returns_empty_for_empty_corpus():
    index = BM25Index([])

    assert index.search("任何问题") == []
