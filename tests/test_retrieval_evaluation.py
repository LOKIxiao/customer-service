from app.rag.document_loader import DocumentLoader
from app.rag.evaluation import evaluate, load_dataset
from app.schemas.rag import RetrievedChunk


class StaticRetriever:
    def retrieve(self, query: str, top_k: int = 3):
        return [
            RetrievedChunk(
                chunk_id="refund_policy.md:5",
                source="refund_policy.md",
                content="退款关联规则",
                score=0.9,
            ),
            RetrievedChunk(
                chunk_id="refund_policy.md:2",
                source="refund_policy.md",
                content="退款1-3个工作日原路退回",
                score=0.8,
            ),
        ]


def test_evaluate_distinguishes_source_hit_from_evidence_hit():
    result = evaluate(
        StaticRetriever(),
        [
            {
                "query": "退款多久",
                "expected_source": "refund_policy.md",
                "expected_chunk_ids": ["refund_policy.md:2"],
            }
        ],
        k=3,
    )

    assert result["source_recall@k"] == 1.0
    assert result["source_mrr"] == 1.0
    assert result["evidence_recall@k"] == 1.0
    assert result["evidence_mrr"] == 0.5
    assert result["answerable_total"] == 1


def test_evaluate_scores_unanswerable_rejection_separately():
    result = evaluate(
        StaticRetriever(),
        [
            {
                "query": "知识库里没有的问题",
                "answerable": False,
                "expected_source": None,
                "expected_chunk_ids": [],
            }
        ],
        k=3,
    )

    assert result["answerable_total"] == 0
    assert result["unanswerable_total"] == 1
    assert result["unanswerable_rejection_accuracy"] == 0.0


def test_all_evidence_labels_reference_existing_chunks():
    chunk_ids = {chunk.chunk_id for chunk in DocumentLoader().load()}
    dataset = load_dataset()

    positives = [item for item in dataset if item["answerable"]]
    negatives = [item for item in dataset if not item["answerable"]]
    unique_gold_chunks = {
        chunk_id for item in positives for chunk_id in item["expected_chunk_ids"]
    }

    assert len(dataset) == 140
    assert len(positives) == 123
    assert len(negatives) == 17
    assert len(unique_gold_chunks) >= 100
    assert sum(item["query_type"] == "multi_evidence" for item in positives) == 20
    assert all(item["expected_chunk_ids"] for item in positives)
    assert all(not item["expected_chunk_ids"] for item in negatives)
    assert all(item["annotation_status"] == "draft_pending_human_review" for item in dataset)
    assert all(
        chunk_id in chunk_ids
        for item in positives
        for chunk_id in item["expected_chunk_ids"]
    )
