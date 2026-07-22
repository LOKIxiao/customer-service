from app.mcp import handlers
from app.memory.long_term_store import UserMemoryStore
from app.rag.embedding import FakeEmbeddingClient
from app.rag.factory import create_retriever


def test_handle_get_order_found():
    result = handlers.handle_get_order(user_id="u_001")

    assert result["found"] is True
    assert result["order"]["order_id"] == "A10001"


def test_handle_get_order_not_found():
    result = handlers.handle_get_order(user_id="u_001", order_id="A10002")

    assert result["found"] is False
    assert result["order"] is None


def test_handle_create_and_query_ticket(tmp_path):
    tickets_file = tmp_path / "mock_tickets.json"

    created = handlers.handle_create_ticket(
        user_id="u_test", content="商品坏了", tickets_file=tickets_file
    )
    assert created["status"] == "pending"

    queried = handlers.handle_query_ticket(user_id="u_test", tickets_file=tickets_file)
    assert queried["found"] is True
    assert queried["ticket"]["ticket_id"] == created["ticket_id"]


def test_handle_query_ticket_not_found(tmp_path):
    tickets_file = tmp_path / "mock_tickets.json"

    result = handlers.handle_query_ticket(user_id="u_none", tickets_file=tickets_file)

    assert result["found"] is False
    assert result["ticket"] is None


def test_handle_search_knowledge_base(tmp_path):
    kb_dir = tmp_path / "knowledge_base"
    kb_dir.mkdir()
    (kb_dir / "refund_policy.md").write_text(
        "# 退款政策\n\n退款会在 1-3 个工作日内原路退回。",
        encoding="utf-8",
    )

    retriever = create_retriever(
        knowledge_dir=kb_dir,
        embedding_client=FakeEmbeddingClient(),
        persist_directory=tmp_path / "chroma",
    )

    result = handlers.handle_search_knowledge_base(query="退款多久到账？", retriever=retriever)

    assert result["chunks"]
    assert result["chunks"][0]["source"] == "refund_policy.md"


def test_handle_review_compliance_redacts_phone():
    result = handlers.handle_review_compliance("我的手机号是13800001111")

    assert "****" in result["response"]
    assert result["need_human"] is False


def test_handle_review_compliance_flags_risk_keywords():
    result = handlers.handle_review_compliance("我要投诉，还要起诉你们")

    assert result["need_human"] is True


def test_handle_save_and_recall_user_memory(tmp_path):
    store = UserMemoryStore(FakeEmbeddingClient(), persist_directory=tmp_path / "user_memory")

    saved = handlers.handle_save_user_memory(
        user_id="u_001",
        category="preference",
        content="用户偏好无线降噪耳机，更看重续航",
        store=store,
    )
    assert saved["user_id"] == "u_001"

    result = handlers.handle_recall_user_memory(
        user_id="u_001",
        query="耳机偏好是什么",
        store=store,
    )

    assert result["memories"]
    assert result["memories"][0]["content"] == "用户偏好无线降噪耳机，更看重续航"


def test_handle_recall_user_memory_empty_for_unknown_user(tmp_path):
    store = UserMemoryStore(FakeEmbeddingClient(), persist_directory=tmp_path / "user_memory")

    result = handlers.handle_recall_user_memory(user_id="u_none", query="随便问点什么", store=store)

    assert result["memories"] == []
