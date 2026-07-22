from pathlib import Path
from typing import Any

from app.agents.compliance_agent import ComplianceAgent
from app.memory.factory import create_memory_store
from app.memory.long_term_store import UserMemoryStore
from app.rag.factory import create_retriever
from app.rag.hybrid_retriever import HybridKnowledgeRetriever
from app.tools.order_tools import get_latest_order_by_user, get_order_by_id
from app.tools.ticket_tools import TICKETS_FILE, create_ticket, get_latest_ticket_by_user

# 这里是 server 和 FakeMCPToolClient 共用的纯业务逻辑，
# MCP 协议层（app/mcp/server.py）只是薄薄包一层 @mcp.tool()。

_compliance_agent = ComplianceAgent()
_default_retriever: HybridKnowledgeRetriever | None = None
_default_memory_store: UserMemoryStore | None = None


def _resolve_retriever(
    retriever: HybridKnowledgeRetriever | None,
    persist_directory: Path | None = None,
) -> HybridKnowledgeRetriever:
    global _default_retriever

    if retriever is not None:
        return retriever

    if _default_retriever is None:
        _default_retriever = create_retriever(persist_directory=persist_directory)

    return _default_retriever


def _resolve_memory_store(
    store: UserMemoryStore | None,
    persist_directory: Path | None = None,
) -> UserMemoryStore:
    global _default_memory_store

    if store is not None:
        return store

    if _default_memory_store is None:
        _default_memory_store = create_memory_store(persist_directory=persist_directory)

    return _default_memory_store


def handle_get_order(user_id: str, order_id: str | None = None) -> dict[str, Any]:
    if order_id:
        order = get_order_by_id(user_id=user_id, order_id=order_id)
    else:
        order = get_latest_order_by_user(user_id=user_id)

    return {"found": order is not None, "order": order}


def handle_create_ticket(
    user_id: str,
    content: str,
    tickets_file: Path | None = None,
) -> dict[str, Any]:
    return create_ticket(
        user_id=user_id,
        content=content,
        file_path=tickets_file or TICKETS_FILE,
    )


def handle_query_ticket(
    user_id: str,
    tickets_file: Path | None = None,
) -> dict[str, Any]:
    ticket = get_latest_ticket_by_user(
        user_id=user_id,
        file_path=tickets_file or TICKETS_FILE,
    )

    return {"found": ticket is not None, "ticket": ticket}


def handle_search_knowledge_base(
    query: str,
    top_k: int = 3,
    retriever: HybridKnowledgeRetriever | None = None,
    persist_directory: Path | None = None,
) -> dict[str, Any]:
    chunks = _resolve_retriever(retriever, persist_directory=persist_directory).retrieve(
        query=query, top_k=top_k
    )

    return {"chunks": [chunk.model_dump() for chunk in chunks]}


def handle_review_compliance(text: str) -> dict[str, Any]:
    return _compliance_agent.review(text).model_dump()


def handle_recall_user_memory(
    user_id: str,
    query: str,
    top_k: int = 3,
    store: UserMemoryStore | None = None,
    persist_directory: Path | None = None,
) -> dict[str, Any]:
    memories = _resolve_memory_store(store, persist_directory=persist_directory).search_memories(
        user_id=user_id, query=query, top_k=top_k
    )

    return {"memories": [memory.model_dump() for memory in memories]}


def handle_save_user_memory(
    user_id: str,
    category: str,
    content: str,
    store: UserMemoryStore | None = None,
    persist_directory: Path | None = None,
) -> dict[str, Any]:
    record = _resolve_memory_store(store, persist_directory=persist_directory).add_memory(
        user_id=user_id, category=category, content=content
    )

    return record.model_dump()
