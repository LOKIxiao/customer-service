from app.rag.bm25 import BM25Index
from app.rag.document_loader import DocumentLoader
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
    ) -> None:
        self.document_loader = document_loader
        self.vector_store = vector_store
        self.candidate_k = candidate_k
        self.rrf_k = rrf_k
        self._bm25: BM25Index | None = None
        self._is_loaded = False

    def retrieve(self, query: str, top_k: int = 3) -> list[RetrievedChunk]:
        self._ensure_loaded()

        vector_hits = self.vector_store.search(query=query, top_k=self.candidate_k)
        bm25_hits = self._bm25.search(query=query, top_k=self.candidate_k)

        fused_scores: dict[str, float] = {}
        chunk_by_id: dict[str, DocumentChunk] = {}

        for rank, hit in enumerate(vector_hits):
            fused_scores[hit.chunk_id] = fused_scores.get(hit.chunk_id, 0.0) + 1 / (self.rrf_k + rank + 1)
            chunk_by_id[hit.chunk_id] = hit

        for rank, (chunk, _bm25_score) in enumerate(bm25_hits):
            fused_scores[chunk.chunk_id] = fused_scores.get(chunk.chunk_id, 0.0) + 1 / (self.rrf_k + rank + 1)
            chunk_by_id.setdefault(chunk.chunk_id, chunk)

        ranked_ids = sorted(fused_scores, key=lambda chunk_id: fused_scores[chunk_id], reverse=True)[:top_k]

        return [
            RetrievedChunk(
                chunk_id=chunk_id,
                source=chunk_by_id[chunk_id].source,
                content=chunk_by_id[chunk_id].content,
                metadata=chunk_by_id[chunk_id].metadata,
                score=fused_scores[chunk_id],
            )
            for chunk_id in ranked_ids
        ]

    def _ensure_loaded(self) -> None:
        if self._is_loaded:
            return

        chunks = self.document_loader.load()
        self.vector_store.add_chunks(chunks)
        self._bm25 = BM25Index(chunks)
        self._is_loaded = True
