import json
from pathlib import Path
from typing import Any

from app.rag.chroma_vector_store import ChromaVectorStore
from app.rag.document_loader import DocumentLoader
from app.rag.embedding import EmbeddingClient
from app.rag.embedding_factory import create_embedding_client
from app.rag.factory import create_reranker
from app.rag.hybrid_retriever import HybridKnowledgeRetriever
from app.rag.retriever import KnowledgeRetriever
from app.rag.vector_store import InMemoryVectorStore

DEFAULT_DATASET = Path("data/eval/retrieval_qa.json")
DEFAULT_KNOWLEDGE_DIR = Path("data/knowledge_base")
# 评估脚本用的 chroma 索引和生产用的 data/chroma_db 分开，避免互相污染
DEFAULT_EVAL_PERSIST_DIR = Path("data/chroma_db_eval")


def load_dataset(path: Path = DEFAULT_DATASET) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate(retriever, dataset: list[dict], k: int = 3) -> dict[str, Any]:
    """评估可回答样本的召回，并单独评估无答案样本的拒绝能力。"""
    source_hits = 0
    source_reciprocal_ranks: list[float] = []
    evidence_hits = 0
    evidence_reciprocal_ranks: list[float] = []
    answerable_total = 0
    unanswerable_total = 0
    unanswerable_rejections = 0

    for item in dataset:
        results = retriever.retrieve(item["query"], top_k=k)
        if not item.get("answerable", True):
            unanswerable_total += 1
            if not results:
                unanswerable_rejections += 1
            continue

        answerable_total += 1
        sources = [chunk.source for chunk in results]
        chunk_ids = [chunk.chunk_id for chunk in results]

        expected_sources = set(item.get("expected_sources") or [item["expected_source"]])
        source_ranks = [
            sources.index(source) + 1 for source in expected_sources if source in sources
        ]
        source_match_mode = item.get("match_mode", "any")
        source_matched = (
            len(source_ranks) == len(expected_sources)
            if source_match_mode == "all"
            else bool(source_ranks)
        )
        if source_matched:
            source_hits += 1
            rank = max(source_ranks) if source_match_mode == "all" else min(source_ranks)
            source_reciprocal_ranks.append(1 / rank)
        else:
            source_reciprocal_ranks.append(0.0)

        expected_chunk_ids = set(item["expected_chunk_ids"])
        evidence_ranks = [
            chunk_ids.index(chunk_id) + 1
            for chunk_id in expected_chunk_ids
            if chunk_id in chunk_ids
        ]
        match_mode = item.get("match_mode", "any")
        evidence_matched = (
            len(evidence_ranks) == len(expected_chunk_ids)
            if match_mode == "all"
            else bool(evidence_ranks)
        )
        evidence_rank = (
            max(evidence_ranks) if match_mode == "all" else min(evidence_ranks)
        ) if evidence_matched else None
        if evidence_rank is not None:
            evidence_hits += 1
            evidence_reciprocal_ranks.append(1 / evidence_rank)
        else:
            evidence_reciprocal_ranks.append(0.0)

    unique_evidence_chunks = {
        chunk_id
        for item in dataset
        if item.get("answerable", True)
        for chunk_id in item["expected_chunk_ids"]
    }
    return {
        "source_recall@k": source_hits / answerable_total if answerable_total else 0.0,
        "source_mrr": (
            sum(source_reciprocal_ranks) / answerable_total if answerable_total else 0.0
        ),
        "evidence_recall@k": evidence_hits / answerable_total if answerable_total else 0.0,
        "evidence_mrr": (
            sum(evidence_reciprocal_ranks) / answerable_total if answerable_total else 0.0
        ),
        "unanswerable_rejection_accuracy": (
            unanswerable_rejections / unanswerable_total if unanswerable_total else None
        ),
        "k": k,
        "total": len(dataset),
        "answerable_total": answerable_total,
        "unanswerable_total": unanswerable_total,
        "unique_evidence_chunks": len(unique_evidence_chunks),
    }


def _build_retrievers(
    embedding_client: EmbeddingClient,
    knowledge_dir: Path = DEFAULT_KNOWLEDGE_DIR,
    persist_root: Path = DEFAULT_EVAL_PERSIST_DIR,
) -> dict[str, Any]:
    retrievers = {
        "naive（InMemory，向量only）": KnowledgeRetriever(
            document_loader=DocumentLoader(knowledge_dir=knowledge_dir),
            vector_store=InMemoryVectorStore(embedding_client),
        ),
        "chroma（向量only）": KnowledgeRetriever(
            document_loader=DocumentLoader(knowledge_dir=knowledge_dir),
            vector_store=ChromaVectorStore(
                embedding_client, persist_directory=persist_root / "vector_only"
            ),
        ),
        "chroma + BM25（混合检索）": HybridKnowledgeRetriever(
            document_loader=DocumentLoader(knowledge_dir=knowledge_dir),
            vector_store=ChromaVectorStore(
                embedding_client, persist_directory=persist_root / "hybrid"
            ),
        ),
    }
    reranker = create_reranker()
    if reranker:
        retrievers["RRF Top20 + qwen3-rerank"] = HybridKnowledgeRetriever(
            document_loader=DocumentLoader(knowledge_dir=knowledge_dir),
            vector_store=ChromaVectorStore(
                embedding_client, persist_directory=persist_root / "reranked"
            ),
            candidate_k=20,
            reranker=reranker,
            rerank_candidate_k=20,
        )
    return retrievers


def run_comparison(k: int = 3, dataset_path: Path = DEFAULT_DATASET) -> None:
    dataset = load_dataset(dataset_path)
    embedding_client = create_embedding_client()
    retrievers = _build_retrievers(embedding_client)

    positive_total = sum(item.get("answerable", True) for item in dataset)
    unique_evidence = len(
        {
            chunk_id
            for item in dataset
            if item.get("answerable", True)
            for chunk_id in item["expected_chunk_ids"]
        }
    )
    print(
        f"评估数据集: {dataset_path}（{len(dataset)} 条：正例 {positive_total}，"
        f"无答案 {len(dataset) - positive_total}，覆盖证据 {unique_evidence}），"
        f"embedding={type(embedding_client).__name__}，top_k={k}\n"
    )
    print(
        f"{'配置':<24}{'来源R@K':>10}{'来源MRR':>10}{'证据R@K':>10}"
        f"{'证据MRR':>10}{'拒答准确率':>12}"
    )
    print("-" * 76)

    for name, retriever in retrievers.items():
        result = evaluate(retriever, dataset, k=k)
        rejection = result["unanswerable_rejection_accuracy"]
        rejection_text = f"{rejection * 100:.1f}%" if rejection is not None else "N/A"
        print(
            f"{name:<24}"
            f"{result['source_recall@k'] * 100:>9.1f}%"
            f"{result['source_mrr']:>10.3f}"
            f"{result['evidence_recall@k'] * 100:>9.1f}%"
            f"{result['evidence_mrr']:>10.3f}"
            f"{rejection_text:>12}"
        )


if __name__ == "__main__":
    run_comparison()
