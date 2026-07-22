import math
from collections import Counter

import jieba

from app.schemas.rag import DocumentChunk


def _tokenize(text: str) -> list[str]:
    return [token for token in jieba.cut_for_search(text) if token.strip()]


class BM25Index:
    """标准 BM25（Okapi BM25）关键词检索，手写实现，配合向量检索做混合召回。"""

    def __init__(self, chunks: list[DocumentChunk], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.chunks = chunks

        self._doc_tokens = [_tokenize(chunk.content) for chunk in chunks]
        self._doc_len = [len(tokens) for tokens in self._doc_tokens]
        self._avg_len = sum(self._doc_len) / len(self._doc_len) if self._doc_len else 0.0

        self._doc_freq: Counter[str] = Counter()
        for tokens in self._doc_tokens:
            for term in set(tokens):
                self._doc_freq[term] += 1

        self._n = len(chunks)

    def _idf(self, term: str) -> float:
        df = self._doc_freq.get(term, 0)
        return math.log((self._n - df + 0.5) / (df + 0.5) + 1)

    def search(self, query: str, top_k: int = 10) -> list[tuple[DocumentChunk, float]]:
        if not self.chunks:
            return []

        query_terms = _tokenize(query)
        scored: list[tuple[DocumentChunk, float]] = []

        for idx, tokens in enumerate(self._doc_tokens):
            term_counts = Counter(tokens)
            doc_len = self._doc_len[idx]
            score = 0.0

            for term in query_terms:
                freq = term_counts.get(term, 0)
                if freq == 0:
                    continue

                idf = self._idf(term)
                denom = freq + self.k1 * (1 - self.b + self.b * doc_len / (self._avg_len or 1))
                score += idf * (freq * (self.k1 + 1)) / denom

            if score > 0:
                scored.append((self.chunks[idx], score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]
