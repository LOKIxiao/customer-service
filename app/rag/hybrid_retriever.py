from app.rag.bm25 import BM25Index
from app.rag.document_loader import DocumentLoader
from app.rag.evidence_gate import EvidenceGate
from app.rag.reranker import BaseReranker
from app.schemas.rag import DocumentChunk, RetrievedChunk


class HybridKnowledgeRetriever:
    """向量检索 + BM25 关键词检索，用 RRF（Reciprocal Rank Fusion）融合两路候选。

    向量检索擅长语义相近但用词不同的问法，BM25 擅长关键词精确命中；
    RRF 不需要对两路分数做归一化调参，只看排名，简单且稳健。
    """

    def __init__(
        self,
        document_loader: DocumentLoader,
        vector_store,
        candidate_k: int = 10,
        rrf_k: int = 60,
        evidence_gate: EvidenceGate | None = None,
        reranker: BaseReranker | None = None,
        rerank_candidate_k: int = 20,
    ) -> None:
        self.document_loader = document_loader
        self.vector_store = vector_store
        self.candidate_k = candidate_k
        self.rrf_k = rrf_k
        self.evidence_gate = evidence_gate
        self.reranker = reranker
        self.rerank_candidate_k = rerank_candidate_k
        self._bm25: BM25Index | None = None
        self._is_loaded = False

    def retrieve(self, query: str, top_k: int = 3) -> list[RetrievedChunk]:
        self._ensure_loaded()

        vector_hits = self.vector_store.search(query=query, top_k=self.candidate_k)
        bm25_hits = self._bm25.search(query=query, top_k=self.candidate_k)

        fused_scores: dict[str, float] = {}
        chunk_by_id: dict[str, DocumentChunk] = {}
        vector_scores: dict[str, float] = {}
        bm25_scores: dict[str, float] = {}

        for rank, hit in enumerate(vector_hits):
            fused_scores[hit.chunk_id] = fused_scores.get(hit.chunk_id, 0.0) + 1 / (self.rrf_k + rank + 1)
            chunk_by_id[hit.chunk_id] = hit
            vector_scores[hit.chunk_id] = hit.score

        for rank, (chunk, bm25_score) in enumerate(bm25_hits):
            fused_scores[chunk.chunk_id] = fused_scores.get(chunk.chunk_id, 0.0) + 1 / (self.rrf_k + rank + 1)
            chunk_by_id.setdefault(chunk.chunk_id, chunk)
            bm25_scores[chunk.chunk_id] = bm25_score

        pool_size = max(top_k, self.rerank_candidate_k) if self.reranker else top_k
        ranked_ids = sorted(
            fused_scores,
            key=lambda chunk_id: fused_scores[chunk_id],
            reverse=True,
        )[:pool_size]

        results = [
            RetrievedChunk(
                chunk_id=chunk_id,
                source=chunk_by_id[chunk_id].source,
                content=chunk_by_id[chunk_id].content,
                metadata={
                    **chunk_by_id[chunk_id].metadata,
                    "retrieval": {
                        "vector_score": vector_scores.get(chunk_id),
                        "bm25_score": bm25_scores.get(chunk_id),
                    },
                },
                score=fused_scores[chunk_id],
            )
            for chunk_id in ranked_ids
        ]

        if self.reranker:
            results = self.reranker.rerank(query, results, top_k=top_k)
        else:
            results = results[:top_k]

        if self.evidence_gate and not self.evidence_gate.evaluate(query, results).sufficient:
            return []

        return results

    def _ensure_loaded(self) -> None:
        if self._is_loaded:
            return

        chunks = self.document_loader.load()
        self.vector_store.add_chunks(chunks)
        self._bm25 = BM25Index(chunks)
        self._is_loaded = True
