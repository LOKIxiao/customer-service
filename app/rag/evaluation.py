import json
from pathlib import Path
from typing import Any

from app.rag.chroma_vector_store import ChromaVectorStore
from app.rag.document_loader import DocumentLoader
from app.rag.embedding import EmbeddingClient
from app.rag.embedding_factory import create_embedding_client
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
    """计算 recall@k（top-k 里有没有命中 expected_source）和 MRR（首次命中排名的倒数均值）。"""
    hits = 0
    reciprocal_ranks: list[float] = []

    for item in dataset:
        results = retriever.retrieve(item["query"], top_k=k)
        sources = [chunk.source for chunk in results]

        if item["expected_source"] in sources:
            hits += 1
            rank = sources.index(item["expected_source"]) + 1
            reciprocal_ranks.append(1 / rank)
        else:
            reciprocal_ranks.append(0.0)

    total = len(dataset)
    return {
        "recall@k": hits / total if total else 0.0,
        "mrr": sum(reciprocal_ranks) / total if total else 0.0,
        "k": k,
        "total": total,
    }


def _build_retrievers(
    embedding_client: EmbeddingClient,
    knowledge_dir: Path = DEFAULT_KNOWLEDGE_DIR,
    persist_root: Path = DEFAULT_EVAL_PERSIST_DIR,
) -> dict[str, Any]:
    return {
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


def run_comparison(k: int = 3, dataset_path: Path = DEFAULT_DATASET) -> None:
    dataset = load_dataset(dataset_path)
    embedding_client = create_embedding_client()
    retrievers = _build_retrievers(embedding_client)

    print(f"评估数据集: {dataset_path}（{len(dataset)} 条），embedding={type(embedding_client).__name__}，top_k={k}\n")
    print(f"{'配置':<24}{'recall@k':>10}{'MRR':>10}")
    print("-" * 44)

    for name, retriever in retrievers.items():
        result = evaluate(retriever, dataset, k=k)
        print(f"{name:<24}{result['recall@k'] * 100:>9.1f}%{result['mrr']:>10.3f}")


if __name__ == "__main__":
    run_comparison()
