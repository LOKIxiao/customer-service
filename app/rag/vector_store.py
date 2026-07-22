from app.rag.embedding import EmbeddingClient
from app.schemas.rag import DocumentChunk, RetrievedChunk


class InMemoryVectorStore:
    def __init__(self, embedding_client: EmbeddingClient) -> None:
        self.embedding_client = embedding_client
        self._items: list[tuple[DocumentChunk, list[float]]] = []

    def add_chunks(self, chunks: list[DocumentChunk]) -> None:
        for chunk in chunks:
            embedding = self.embedding_client.embed(chunk.content) # 转成向量
            self._items.append((chunk, embedding))

    def search(self, query: str, top_k: int = 3) -> list[RetrievedChunk]:
        if not self._items:
            return []

        query_embedding = self.embedding_client.embed(query)
        scored_items = []

        for chunk, embedding in self._items:
            score = self._cosine_similarity(query_embedding, embedding)
            scored_items.append((chunk, score))

        ranked_items = sorted(
            scored_items,
            key=lambda item: item[1],
            reverse=True,
        )

        return [
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                source=chunk.source,
                content=chunk.content,
                metadata=chunk.metadata,
                score=float(score),
            )
            for chunk, score in ranked_items[:top_k]
            if score > 0
        ]

    # 余弦
    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0

        return sum(a * b for a, b in zip(left, right))