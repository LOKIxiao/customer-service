from app.rag.reranker import QwenReranker
from app.schemas.rag import RetrievedChunk


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "results": [
                {"index": 1, "relevance_score": 0.95},
                {"index": 0, "relevance_score": 0.25},
            ]
        }


class FakeHttpClient:
    def __init__(self):
        self.request = None

    def post(self, endpoint, **kwargs):
        self.request = (endpoint, kwargs)
        return FakeResponse()


def _chunk(chunk_id: str, content: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        source="policy.md",
        content=content,
        score=score,
    )


def test_qwen_reranker_reorders_candidates_and_retains_rrf_score():
    http = FakeHttpClient()
    reranker = QwenReranker(
        api_key="test-key",
        endpoint="https://example.test/reranks",
        http_client=http,
    )
    candidates = [
        _chunk("c1", "退款政策概述", 0.04),
        _chunk("c2", "退款在仓库验收后原路退回", 0.03),
    ]

    results = reranker.rerank("退款怎么退回", candidates, top_k=2)

    assert [chunk.chunk_id for chunk in results] == ["c2", "c1"]
    assert results[0].score == 0.95
    assert results[0].metadata["rerank"]["original_rrf_score"] == 0.03
    assert http.request[1]["json"]["documents"] == [
        "退款政策概述",
        "退款在仓库验收后原路退回",
    ]


def test_qwen_reranker_returns_empty_without_candidates():
    reranker = QwenReranker(
        api_key="test-key",
        endpoint="https://example.test/reranks",
        http_client=FakeHttpClient(),
    )

    assert reranker.rerank("退款", [], top_k=3) == []
