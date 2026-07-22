from pathlib import Path

import chromadb

from app.rag.embedding import EmbeddingClient
from app.schemas.rag import DocumentChunk, RetrievedChunk


class ChromaVectorStore:
    """基于 chromadb 的持久化向量存储，替代 InMemoryVectorStore 的暴力线性扫描余弦相似度。"""

    def __init__(
        self,
        embedding_client: EmbeddingClient,
        persist_directory: Path,
        collection_name: str = "knowledge_base",
    ) -> None:
        self.embedding_client = embedding_client
        self._collection_name = collection_name
        self._client = chromadb.PersistentClient(path=str(persist_directory))
        self._collection = self._get_or_create_collection()

    def _get_or_create_collection(self):
        return self._client.get_or_create_collection(
            self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, chunks: list[DocumentChunk]) -> None:
        if not chunks:
            return

        # 每次全量重建，避免知识库文档改动后遗留孤立的旧 chunk。
        # 这个知识库规模小，重建成本可以忽略；不做增量同步/去重。
        self._client.delete_collection(self._collection_name)
        self._collection = self._get_or_create_collection()

        embeddings = [self.embedding_client.embed(chunk.content) for chunk in chunks]
        self._collection.add(
            ids=[chunk.chunk_id for chunk in chunks],
            embeddings=embeddings,
            documents=[chunk.content for chunk in chunks],
            metadatas=[{**chunk.metadata, "source": chunk.source} for chunk in chunks],
        )

    def search(self, query: str, top_k: int = 3) -> list[RetrievedChunk]:
        if self._collection.count() == 0:
            return []

        query_embedding = self.embedding_client.embed(query)
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        chunks: list[RetrievedChunk] = []
        for chunk_id, document, metadata, distance in zip(
            result["ids"][0],
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
        ):
            metadata = dict(metadata)
            source = metadata.pop("source")
            chunks.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    source=source,
                    content=document,
                    metadata=metadata,
                    score=1.0 - distance,  # cosine distance -> 相似度
                )
            )

        return chunks
