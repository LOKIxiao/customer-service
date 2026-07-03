from app.agents.ticket_agent import TicketAgent


def test_ticket_agent_creates_ticket(tmp_path):
    tickets_file = tmp_path / "mock_tickets.json"
    agent = TicketAgent(tickets_file=tickets_file)

    reply = agent.handle(
        user_id="u_test",
        intent="ticket_create",
        message="我要投诉，商品坏了",
    )

    assert "已为你创建工单" in reply
    assert "待处理" in reply


def test_ticket_agent_queries_latest_ticket(tmp_path):
    tickets_file = tmp_path / "mock_tickets.json"
    agent = TicketAgent(tickets_file=tickets_file)

    agent.handle(
        user_id="u_query_test",
        intent="ticket_create",
        message="我要投诉，商品坏了",
    )

    reply = agent.handle(
        user_id="u_query_test",
        intent="ticket_query",
        message="查询我的工单状态",
    )

    assert "当前状态是待处理" in reply