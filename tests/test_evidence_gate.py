from app.rag.evidence_gate import EvidenceGate
from app.schemas.rag import RetrievedChunk


def _chunk(content: str, vector_score: float | None, bm25_score: float | None):
    return RetrievedChunk(
        chunk_id="c1",
        source="policy.md",
        content=content,
        metadata={
            "retrieval": {
                "vector_score": vector_score,
                "bm25_score": bm25_score,
            }
        },
        score=0.03,
    )


def test_evidence_gate_accepts_semantically_relevant_candidate():
    gate = EvidenceGate(vector_threshold=0.7, bm25_threshold=1.0)

    decision = gate.evaluate("钱怎么退回来", [_chunk("退款将在三天内到账", 0.82, 2.0)])

    assert decision.sufficient is True
    assert decision.reason == "semantic threshold passed"


def test_evidence_gate_accepts_strong_lexical_evidence():
    gate = EvidenceGate(
        vector_threshold=0.9,
        lexical_coverage_threshold=0.5,
        bm25_threshold=1.0,
        lexical_bm25_threshold=1.0,
        strong_bm25_threshold=10.0,
    )

    decision = gate.evaluate("耳机保修期限", [_chunk("蓝牙耳机保修期限为12个月", 0.4, 4.2)])

    assert decision.sufficient is True
    assert decision.reason == "lexical threshold passed"


def test_evidence_gate_rejects_unrelated_candidates():
    gate = EvidenceGate(
        vector_threshold=0.7,
        lexical_coverage_threshold=0.6,
        bm25_threshold=1.0,
        lexical_bm25_threshold=1.0,
        strong_bm25_threshold=10.0,
    )

    decision = gate.evaluate("公司CEO是谁", [_chunk("会员积分兑换政策", 0.35, 0.0)])

    assert decision.sufficient is False


def test_evidence_gate_rejects_empty_results():
    decision = EvidenceGate().evaluate("任何问题", [])

    assert decision.sufficient is False
