from app.agents.llm_intent_agent import LLMIntentAgent


class StaticLLMClient:
    def __init__(self, intent_json: str) -> None:
        self.intent_json = intent_json
        self.last_intent_message = ""

    def generate_customer_reply(
        self, user_message: str, intent: str, raw_reply: str, long_term_context: str = ""
    ) -> str:
        return raw_reply

    def classify_intent(self, message: str) -> str:
        self.last_intent_message = message
        return self.intent_json


def test_llm_intent_agent_parses_valid_json():
    client = StaticLLMClient(
        """
{
  "intent": "order_query",
  "confidence": 0.91,
  "slots": {"order_id": "A10001"},
  "need_clarification": false
}
"""
    )

    agent = LLMIntentAgent(client)

    result = agent.classify("帮我查订单 A10001")

    assert result is not None
    assert result.intent == "order_query"
    assert result.confidence == 0.91
    assert result.slots["order_id"] == "A10001"


def test_llm_intent_agent_rejects_invalid_intent():
    client = StaticLLMClient(
        """
{
  "intent": "invalid_intent",
  "confidence": 0.99,
  "slots": {},
  "need_clarification": false
}
"""
    )

    agent = LLMIntentAgent(client)

    assert agent.classify("xxx") is None


def test_llm_intent_agent_handles_invalid_json():
    client = StaticLLMClient("not json")

    agent = LLMIntentAgent(client)

    assert agent.classify("xxx") is None


def test_llm_intent_agent_includes_recent_history_for_ellipsis_resolution():
    client = StaticLLMClient(
        '{"intent":"knowledge_base_query","confidence":0.9,"slots":{},"need_clarification":false}'
    )
    agent = LLMIntentAgent(client)

    agent.classify(
        "那多久能到账？",
        conversation_history="用户：我刚申请了退款\n客服：已提交退款申请",
    )

    assert "【最近对话】" in client.last_intent_message
    assert "我刚申请了退款" in client.last_intent_message
    assert "【当前用户消息】\n那多久能到账？" in client.last_intent_message
