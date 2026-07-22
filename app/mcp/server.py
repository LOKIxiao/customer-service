import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.mcp.handlers import (
    handle_create_ticket,
    handle_get_order,
    handle_query_ticket,
    handle_recall_user_memory,
    handle_review_compliance,
    handle_save_user_memory,
    handle_search_knowledge_base,
)

mcp = FastMCP("customer-service-tools")


def _tickets_file() -> Path | None:
    # 子进程读环境变量而不是 Python 对象，测试通过 TICKETS_FILE 做隔离
    value = os.getenv("TICKETS_FILE")
    return Path(value) if value else None


def _chroma_persist_directory() -> Path | None:
    value = os.getenv("CHROMA_PERSIST_DIR")
    return Path(value) if value else None


def _user_memory_persist_directory() -> Path | None:
    value = os.getenv("USER_MEMORY_DB_DIR")
    return Path(value) if value else None


@mcp.tool()
def get_order(user_id: str, order_id: str | None = None) -> dict[str, Any]:
    """按 user_id（可选 order_id）查询订单，返回 found 标记和订单详情。"""
    return handle_get_order(user_id=user_id, order_id=order_id)


@mcp.tool()
def create_ticket(user_id: str, content: str) -> dict[str, Any]:
    """为用户创建一个新的投诉/工单。"""
    return handle_create_ticket(user_id=user_id, content=content, tickets_file=_tickets_file())


@mcp.tool()
def query_ticket(user_id: str) -> dict[str, Any]:
    """查询用户最近一条工单的状态。"""
    return handle_query_ticket(user_id=user_id, tickets_file=_tickets_file())


@mcp.tool()
def search_knowledge_base(query: str, top_k: int = 3) -> dict[str, Any]:
    """在知识库中做向量+关键词混合检索，返回命中的文档片段。"""
    return handle_search_knowledge_base(
        query=query,
        top_k=top_k,
        persist_directory=_chroma_persist_directory(),
    )


@mcp.tool()
def review_compliance(text: str) -> dict[str, Any]:
    """对客服回复做合规审查：手机号脱敏、风险关键词识别。"""
    return handle_review_compliance(text=text)


@mcp.tool()
def recall_user_memory(user_id: str, query: str, top_k: int = 3) -> dict[str, Any]:
    """检索这个用户的长期记忆（商品偏好、收货联系偏好、投诉历史、沟通风格等）。"""
    return handle_recall_user_memory(
        user_id=user_id,
        query=query,
        top_k=top_k,
        persist_directory=_user_memory_persist_directory(),
    )


@mcp.tool()
def save_user_memory(user_id: str, category: str, content: str) -> dict[str, Any]:
    """把一条抽取出的用户长期记忆存下来。"""
    return handle_save_user_memory(
        user_id=user_id,
        category=category,
        content=content,
        persist_directory=_user_memory_persist_directory(),
    )


if __name__ == "__main__":
    mcp.run()
