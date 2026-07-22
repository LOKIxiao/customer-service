from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    chunk_id: str
    source: str
    content: str
    metadata: dict = Field(default_factory=dict)


class RetrievedChunk(DocumentChunk):
    score: float


class RAGResult(BaseModel):
    answer: str
    sources: list[str]
    used_contexts: list[str]