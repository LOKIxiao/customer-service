from pathlib import Path
from typing import Any

from app.mcp import handlers
from app.memory.long_term_store import UserMemoryStore
from app.rag.retriever import KnowledgeRetriever


class FakeMCPToolClient:
    """同进程直接调用 handlers.py，不走真实 stdio 协议，用于快速单测。"""

    def __init__(
        self,
        tickets_file: Path | None = None,
        retriever: KnowledgeRetriever | None = None,
        memory_store: UserMemoryStore | None = None,
    ) -> None:
        self.tickets_file = tickets_file
        self.retriever = retriever
        self.memory_store = memory_store

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if name == "get_order":
            return handlers.handle_get_order(**arguments)

        if name == "create_ticket":
            return handlers.handle_create_ticket(tickets_file=self.tickets_file, **arguments)

        if name == "query_ticket":
            return handlers.handle_query_ticket(tickets_file=self.tickets_file, **arguments)

        if name == "search_knowledge_base":
            return handlers.handle_search_knowledge_base(retriever=self.retriever, **arguments)

        if name == "review_compliance":
            return handlers.handle_review_compliance(**arguments)

        if name == "recall_user_memory":
            return handlers.handle_recall_user_memory(store=self.memory_store, **arguments)

        if name == "save_user_memory":
            return handlers.handle_save_user_memory(store=self.memory_store, **arguments)

        raise ValueError(f"Unknown MCP tool: {name}")

    def close(self) -> None:
        return None
