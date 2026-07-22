import pytest

from app.mcp.client import MCPToolClient

# 这里不 mock 任何东西：真正起一个 stdio 子进程连 app/mcp/server.py，
# 用来证明 MCP 协议（JSON-RPC + tool schema + session）是真的打通的。
# 其余 Agent 单测走 FakeMCPToolClient，只有这个文件覆盖真实传输层。


@pytest.fixture
def mcp_client(tmp_path):
    # 集成测试只验证协议/传输层真的打通，不依赖真实网络和 API Key，
    # 所以强制 server 子进程走 FakeEmbeddingClient。
    client = MCPToolClient(
        tickets_file=tmp_path / "mock_tickets.json",
        env_overrides={
            "EMBEDDING_ENABLED": "false",
            "CHROMA_PERSIST_DIR": str(tmp_path / "chroma"),
            "USER_MEMORY_DB_DIR": str(tmp_path / "user_memory"),
        },
    )
    yield client
    client.close()


def test_real_mcp_client_gets_order(mcp_client):
    result = mcp_client.call_tool("get_order", {"user_id": "u_001"})

    assert result["found"] is True
    assert result["order"]["order_id"] == "A10001"


def test_real_mcp_client_creates_and_queries_ticket(mcp_client):
    created = mcp_client.call_tool(
        "create_ticket", {"user_id": "u_real", "content": "测试工单"}
    )
    assert created["status"] == "pending"

    queried = mcp_client.call_tool("query_ticket", {"user_id": "u_real"})
    assert queried["found"] is True
    assert queried["ticket"]["ticket_id"] == created["ticket_id"]


def test_real_mcp_client_searches_knowledge_base(mcp_client):
    result = mcp_client.call_tool("search_knowledge_base", {"query": "怎么退款"})

    assert result["chunks"]


def test_real_mcp_client_reviews_compliance(mcp_client):
    result = mcp_client.call_tool(
        "review_compliance", {"text": "我的手机号是13800001111"}
    )

    assert "****" in result["response"]


def test_real_mcp_client_saves_and_recalls_user_memory(mcp_client):
    saved = mcp_client.call_tool(
        "save_user_memory",
        {"user_id": "u_real", "category": "preference", "content": "用户偏好无线降噪耳机"},
    )
    assert saved["user_id"] == "u_real"

    result = mcp_client.call_tool(
        "recall_user_memory", {"user_id": "u_real", "query": "耳机偏好是什么"}
    )

    assert result["memories"]
