from app.agents.response_agent import ResponseAgent
from app.llm.fake_client import FakeLLMClient


def test_response_agent_uses_fake_llm_client():
    agent = ResponseAgent(FakeLLMClient())

    result = agent.generate(
        user_message="我的订单什么时候到？",
        intent="order_query",
        raw_reply="你的订单已发货。",
    )

    assert result == "你的订单已发货。"


class BrokenLLMClient:
    def generate_customer_reply(
        self,
        user_message: str,
        intent: str,
        raw_reply: str,
        long_term_context: str = "",
    ) -> str:
        raise RuntimeError("LLM service unavailable")


def test_response_agent_fallbacks_to_raw_reply_when_llm_fails():
    agent = ResponseAgent(BrokenLLMClient())

    result = agent.generate(
        user_message="我的订单什么时候到？",
        intent="order_query",
        raw_reply="你的订单已发货。",
    )

    assert result == "你的订单已发货。"
