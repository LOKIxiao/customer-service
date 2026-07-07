from app.agents.llm_intent_agent import LLMIntentAgent


class StaticLLMClient:
    def __init__(self, intent_json: str) -> None:
        self.intent_json = intent_json

    def generate_customer_reply(self, user_message: str, intent: str, raw_reply: str) -> str:
        return raw_reply

    def classify_intent(self, message: str) -> str:
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