from app.agents.supervisor import Supervisor
from app.schemas.chat import ChatRequest


def test_supervisor_handles_order_query():
    supervisor = Supervisor()

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


def test_supervisor_handles_refund_policy():
    supervisor = Supervisor()

    response = supervisor.handle(
        ChatRequest(
            user_id="u_001",
            session_id="s_001",
            message="怎么退款？",
        )
    )

    assert response.intent == "refund_policy"
    assert "7 天" in response.reply
    assert response.trace == [
        "ChatAPI",
        "Supervisor",
        "IntentAgent",
        "RefundPolicyAgent",
        "KnowledgeBase",
        "ComplianceAgent",
    ]

def test_supervisor_handles_ticket_create(tmp_path):
    tickets_file = tmp_path / "mock_tickets.json"
    supervisor = Supervisor(tickets_file=tickets_file)

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
    assert "TicketTools" in response.trace
