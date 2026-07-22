import uuid
from pathlib import Path

import chromadb

from app.rag.embedding import EmbeddingClient
from app.schemas.memory import RetrievedMemory, UserMemoryRecord


class UserMemoryStore:
    """长期用户记忆，按 user_id 隔离的持久化向量存储（复用 chromadb，独立于 RAG 知识库的 collection）。"""

    def __init__(
        self,
        embedding_client: EmbeddingClient,
        persist_directory: Path,
        collection_name: str = "user_memory",
    ) -> None:
        self.embedding_client = embedding_client
        self._client = chromadb.PersistentClient(path=str(persist_directory))
        self._collection = self._client.get_or_create_collection(
            collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_memory(self, user_id: str, category: str, content: str) -> UserMemoryRecord:
        memory_id = f"{user_id}:{uuid.uuid4().hex[:12]}"
        embedding = self.embedding_client.embed(content)

        self._collection.add(
            ids=[memory_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[{"user_id": user_id, "category": category}],
        )

        return UserMemoryRecord(
            memory_id=memory_id,
            user_id=user_id,
            category=category,
            content=content,
        )

    def search_memories(self, user_id: str, query: str, top_k: int = 3) -> list[RetrievedMemory]:
        if self._collection.count() == 0:
            return []

        query_embedding = self.embedding_client.embed(query)
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where={"user_id": user_id},
            include=["documents", "metadatas", "distances"],
        )

        ids = result["ids"][0]
        if not ids:
            return []

        return [
            RetrievedMemory(
                memory_id=memory_id,
                user_id=user_id,
                category=metadata["category"],
                content=document,
                score=1.0 - distance,
            )
            for memory_id, document, metadata, distance in zip(
                ids,
                result["documents"][0],
                result["metadatas"][0],
                result["distances"][0],
            )
        ]
