from app.rag.document_loader import DocumentLoader
from app.rag.vector_store import InMemoryVectorStore
from app.schemas.rag import RetrievedChunk


class KnowledgeRetriever:
    def __init__(self, document_loader: DocumentLoader, vector_store: InMemoryVectorStore) -> None:
        self.document_loader = document_loader
        self.vector_store = vector_store
        self._is_loaded = False
    
    def retrieve(self, query: str, top_k: int = 3) -> list[RetrievedChunk]:
        self._ensure_loaded()
        return self.vector_store.search(query=query, top_k=top_k)
    
    # 懒加载
    def _ensure_loaded(self) -> None:
        if self._is_loaded:
            return

        chunks = self.document_loader.load()
        self.vector_store.add_chunks(chunks)
        self._is_loaded = True
