from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.schemas.rag import RetrievedChunk


DEFAULT_INSTRUCTION = (
    "Given a customer-service question, rank passages by whether they directly "
    "provide the evidence required to answer it. Prefer applicable conditions and "
    "exceptions over passages that only share the same topic."
)


class BaseReranker(ABC):
    @abstractmethod
    def rerank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]:
        """Return at most ``top_k`` candidates ordered by answer relevance."""


class QwenReranker(BaseReranker):
    """Client for the qwen3-rerank compatible HTTP endpoint."""

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        model: str = "qwen3-rerank",
        instruction: str = DEFAULT_INSTRUCTION,
        timeout_seconds: float = 30.0,
        http_client: Any | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("RERANK_API_KEY or LLM_API_KEY is required when reranking is enabled")
        if not endpoint:
            raise ValueError(
                "RERANK_BASE_URL must be the full qwen3-rerank /reranks endpoint"
            )

        self.api_key = api_key
        self.endpoint = endpoint
        self.model = model
        self.instruction = instruction
        self._http = http_client or httpx.Client(timeout=timeout_seconds)

    def rerank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]:
        if not candidates or top_k <= 0:
            return []

        response = self._http.post(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "query": query,
                "documents": [candidate.content for candidate in candidates],
                "top_n": min(top_k, len(candidates)),
                "instruct": self.instruction,
            },
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results")
        if not isinstance(results, list):
            raise ValueError("Rerank response does not contain a results list")

        reranked: list[RetrievedChunk] = []
        for item in results[:top_k]:
            index = int(item["index"])
            if index < 0 or index >= len(candidates):
                raise ValueError(f"Rerank response returned invalid document index: {index}")
            relevance_score = float(item["relevance_score"])
            candidate = candidates[index]
            reranked.append(
                candidate.model_copy(
                    update={
                        "score": relevance_score,
                        "metadata": {
                            **candidate.metadata,
                            "rerank": {
                                "model": self.model,
                                "relevance_score": relevance_score,
                                "original_rrf_score": candidate.score,
                            },
                        },
                    }
                )
            )
        return reranked
