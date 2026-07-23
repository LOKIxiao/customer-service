from app.agents.supervisor import Supervisor
from app.llm.fake_client import FakeLLMClient
from app.mcp.fake_client import FakeMCPToolClient
from app.memory.session_memory import SessionMemory
from app.rag.document_loader import DocumentLoader
from app.rag.embedding import FakeEmbeddingClient
from app.rag.retriever import KnowledgeRetriever
from app.rag.vector_store import InMemoryVectorStore
from app.schemas.chat import ChatRequest


def _fake_retriever() -> KnowledgeRetriever:
    # Supervisor 层的测试只关心图编排是否走通，不关心检索质量，
    # 所以用最轻量的 naive 向量检索，不碰 chroma/磁盘 I/O。
    return KnowledgeRetriever(
        document_loader=DocumentLoader(),
        vector_store=InMemoryVectorStore(FakeEmbeddingClient()),
    )


def _fake_memory_store():
    # 长期记忆没有纯内存实现，用系统临时目录隔离，避免污染 data/user_memory_db
    # 或触发真实 embedding API。
    import tempfile
    from pathlib import Path

    from app.memory.long_term_store import UserMemoryStore

    return UserMemoryStore(
        embedding_client=FakeEmbeddingClient(),
        persist_directory=Path(tempfile.mkdtemp()),
    )


def create_test_supervisor(tickets_file=None, **kwargs):
    return Supervisor(
        llm_client=FakeLLMClient(),
        mcp_client=FakeMCPToolClient(
            tickets_file=tickets_file,
            memory_store=_fake_memory_store(),
            retriever=_fake_retriever(),
        ),
        **kwargs,
    )


def test_supervisor_handles_order_query():
    supervisor = create_test_supervisor()

    response = supervisor.handle(
        ChatRequest(
            user_id="u_001",
            session_id="s_001",
            message="我的订单什么时候到？",
        )
    )

    assert response.intent == "order_query"
    assert "A10001" in response.reply
    assert "Supervisor" in response.trace
    assert "ComplianceAgent" in response.trace


def test_supervisor_handles_knowledge_base_query():
    supervisor = create_test_supervisor()

    response = supervisor.handle(
        ChatRequest(
            user_id="u_001",
            session_id="s_001",
            message="怎么退款？",
        )
    )

    assert response.intent == "knowledge_base_query"
    assert "根据知识库内容" in response.reply
    assert "refund_policy.md" in response.reply
    assert response.trace == [
        "ChatAPI",
        "Supervisor",
        "IntentAgent",
        "RAGAgent",
        "MCP:search_knowledge_base",
        "LongTermMemoryAgent",
        "MCP:recall_user_memory",
        "ResponseAgent",
        "ComplianceAgent",
        "MCP:review_compliance",
        "MemoryExtractionAgent",
    ]


def test_supervisor_routes_membership_question_to_knowledge_base():
    # 回归测试：意图路由扩展之前，这类问题会被分类成 unknown/human_handoff，
    # 根本走不到 RAGAgent，知识库里的 membership_policy.md 就成了摆设。
    supervisor = create_test_supervisor()

    response = supervisor.handle(
        ChatRequest(
            user_id="u_001",
            session_id="s_001",
            message="会员等级怎么算，积分能抵多少钱？",
        )
    )

    assert response.intent == "knowledge_base_query"
    assert "RAGAgent" in response.trace
    assert "MCP:search_knowledge_base" in response.trace
    assert "membership_policy.md" in response.reply


def test_supervisor_routes_troubleshooting_question_to_knowledge_base():
    supervisor = create_test_supervisor()

    response = supervisor.handle(
        ChatRequest(
            user_id="u_001",
            session_id="s_001",
            message="耳机连不上手机怎么办？",
        )
    )

    assert response.intent == "knowledge_base_query"
    assert "troubleshooting_faq.md" in response.reply


def test_supervisor_handles_ticket_create(tmp_path):
    tickets_file = tmp_path / "mock_tickets.json"
    supervisor = create_test_supervisor(tickets_file=tickets_file)

    response = supervisor.handle(
        ChatRequest(
            user_id="u_ticket",
            session_id="s_001",
            message="我要投诉，商品坏了",
        )
    )

    assert response.intent == "ticket_create"
    assert "已为你创建工单" in response.reply
    assert "TicketAgent" in response.trace
    assert "MCP:create_ticket" in response.trace


def test_supervisor_records_conversation_memory():
    memory = SessionMemory()
    supervisor = create_test_supervisor(memory=memory)

    response = supervisor.handle(
        ChatRequest(
            user_id="u_001",
            session_id="s_memory",
            message="我的订单什么时候到？",
        )
    )

    messages = memory.get_messages("s_memory")

    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "我的订单什么时候到？"
    assert messages[1].role == "assistant"
    assert messages[1].content == response.reply


def test_supervisor_handles_memory_query():
    supervisor = create_test_supervisor()

    supervisor.handle(
        ChatRequest(
            user_id="u_001",
            session_id="s_memory_query",
            message="我的订单什么时候到？",
        )
    )

    response = supervisor.handle(
        ChatRequest(
            user_id="u_001",
            session_id="s_memory_query",
            message="刚才我问了什么？",
        )
    )

    assert response.intent == "memory_query"
    assert "我的订单什么时候到？" in response.reply
    assert "MemoryAgent" in response.trace
