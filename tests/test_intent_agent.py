from app.agents.intent_agent import IntentAgent


def test_classifies_order_query():
    agent = IntentAgent()

    result = agent.classify("我的订单什么时候到？")

    assert result.intent == "order_query"


def test_classifies_refund_policy():
    agent = IntentAgent()

    result = agent.classify("怎么退款？")

    assert result.intent == "refund_policy"


def test_classifies_human_handoff():
    agent = IntentAgent()

    result = agent.classify("我要找人工客服")

    assert result.intent == "human_handoff"


def test_extracts_order_id():
    agent = IntentAgent()

    result = agent.classify("帮我查一下订单 A10001")

    assert result.intent == "order_query"
    assert result.slots["order_id"] == "A10001"