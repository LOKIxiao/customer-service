from app.agents.memory_extraction_agent import MemoryExtractionAgent


class StaticLLMClient:
    def __init__(self, facts_json: str) -> None:
        self.facts_json = facts_json

    def generate_customer_reply(
        self, user_message: str, intent: str, raw_reply: str, long_term_context: str = ""
    ) -> str:
        return raw_reply

    def classify_intent(self, message: str) -> str:
        return "{}"

    def extract_user_facts(self, user_message: str, assistant_reply: str) -> str:
        return self.facts_json


def test_memory_extraction_agent_parses_valid_facts():
    client = StaticLLMClient(
        """
{
  "facts": [
    {"category": "preference", "content": "用户偏好无线降噪耳机，更看重续航"}
  ]
}
"""
    )

    agent = MemoryExtractionAgent(client)

    facts = agent.extract("我更喜欢无线降噪的", "好的，已记录您的偏好")

    assert len(facts) == 1
    assert facts[0].category == "preference"
    assert facts[0].content == "用户偏好无线降噪耳机，更看重续航"


def test_memory_extraction_agent_filters_invalid_category():
    client = StaticLLMClient(
        """
{
  "facts": [
    {"category": "not_allowed", "content": "这条不应该被采纳"}
  ]
}
"""
    )

    agent = MemoryExtractionAgent(client)

    assert agent.extract("随便说点什么", "好的") == []


def test_memory_extraction_agent_handles_invalid_json():
    client = StaticLLMClient("not json")

    agent = MemoryExtractionAgent(client)

    assert agent.extract("随便说点什么", "好的") == []


def test_memory_extraction_agent_handles_empty_facts():
    client = StaticLLMClient('{"facts": []}')

    agent = MemoryExtractionAgent(client)

    assert agent.extract("查一下我的物流", "已发货") == []
