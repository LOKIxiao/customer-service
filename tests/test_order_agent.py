from app.agents.order_agent import OrderAgent
from app.mcp.fake_client import FakeMCPToolClient


def test_order_agent_gets_latest_order():
    agent = OrderAgent(mcp_client=FakeMCPToolClient())

    reply = agent.handle(user_id="u_001", slots={})

    assert "A10001" in reply
    assert "蓝牙耳机" in reply
    assert "已发货" in reply


def test_order_agent_blocks_other_user_order():
    agent = OrderAgent(mcp_client=FakeMCPToolClient())

    reply = agent.handle(user_id="u_001", slots={"order_id": "A10002"})

    assert "没有查询到你的订单信息" in reply
