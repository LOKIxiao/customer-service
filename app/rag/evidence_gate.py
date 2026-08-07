from dataclasses import dataclass

from app.rag.bm25 import tokenize
from app.schemas.rag import RetrievedChunk


STOPWORDS = {
    "的", "了", "吗", "呢", "啊", "我", "你", "他", "她", "它", "们",
    "是", "不", "能", "可以", "怎么", "怎样", "什么", "多少", "多久",
    "一下", "如果", "已经", "还是", "一般", "应该", "需要", "时候",
}


@dataclass(frozen=True)
class EvidenceDecision:
    sufficient: bool
    vector_score: float
    bm25_score: float
    lexical_coverage: float
    reason: str


class EvidenceGate:
    """判断Top-K候选是否真的足以回答问题，而不使用只反映名次的RRF分数。"""

    def __init__(
        self,
        vector_threshold: float = 0.75,
        lexical_coverage_threshold: float = 0.3,
        bm25_threshold: float = 9.0,
        lexical_bm25_threshold: float = 0.1,
        strong_bm25_threshold: float = 12.0,
    ) -> None:
        self.vector_threshold = vector_threshold
        self.lexical_coverage_threshold = lexical_coverage_threshold
        self.bm25_threshold = bm25_threshold
        self.lexical_bm25_threshold = lexical_bm25_threshold
        self.strong_bm25_threshold = strong_bm25_threshold

    def evaluate(self, query: str, chunks: list[RetrievedChunk]) -> EvidenceDecision:
        if not chunks:
            return EvidenceDecision(False, 0.0, 0.0, 0.0, "retriever returned no candidates")

        query_terms = {
            term.casefold()
            for term in tokenize(query)
            if len(term.strip()) > 1 and term.casefold() not in STOPWORDS
        }
        best_vector = 0.0
        best_bm25 = 0.0
        best_coverage = 0.0

        for chunk in chunks:
            retrieval = chunk.metadata.get("retrieval", {})
            vector_score = retrieval.get("vector_score")
            bm25_score = retrieval.get("bm25_score")
            best_vector = max(best_vector, float(vector_score or 0.0))
            best_bm25 = max(best_bm25, float(bm25_score or 0.0))

            content = chunk.content.casefold()
            matched = sum(term in content for term in query_terms)
            coverage = matched / len(query_terms) if query_terms else 0.0
            best_coverage = max(best_coverage, coverage)

        semantic_match = (
            best_vector >= self.vector_threshold
            and best_bm25 >= self.bm25_threshold
        )
        lexical_match = (
            best_bm25 >= self.lexical_bm25_threshold
            and best_coverage >= self.lexical_coverage_threshold
        )
        strong_keyword_match = best_bm25 >= self.strong_bm25_threshold
        sufficient = semantic_match or lexical_match or strong_keyword_match
        reason = (
            "semantic threshold passed"
            if semantic_match
            else "lexical threshold passed"
            if lexical_match
            else "strong BM25 threshold passed"
            if strong_keyword_match
            else "no candidate passed semantic or lexical thresholds"
        )
        return EvidenceDecision(
            sufficient=sufficient,
            vector_score=best_vector,
            bm25_score=best_bm25,
            lexical_coverage=best_coverage,
            reason=reason,
        )
