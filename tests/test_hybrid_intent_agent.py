from app.agents.hybrid_intent_agent import HybridIntentAgent
from app.agents.intent_agent import IntentAgent
from app.schemas.intent import IntentResult


class FakeLLMIntentAgent:
    def __init__(self, result):
        self.result = result

    def classify(self, message: str, conversation_history: str = ""):
        return self.result


def test_hybrid_intent_agent_uses_high_confidence_llm_result():
    llm_result = IntentResult(
        intent="knowledge_base_query",
        confidence=0.9,
        slots={},
        need_clarification=False,
    )

    agent = HybridIntentAgent(
        llm_intent_agent=FakeLLMIntentAgent(llm_result),
        rule_intent_agent=IntentAgent(),
    )

    result = agent.classify("我的订单什么时候到？")

    assert result.intent == "knowledge_base_query"


def test_hybrid_intent_agent_fallbacks_to_rule_when_low_confidence():
    llm_result = IntentResult(
        intent="unknown",
        confidence=0.2,
        slots={},
        need_clarification=True,
    )

    agent = HybridIntentAgent(
        llm_intent_agent=FakeLLMIntentAgent(llm_result),
        rule_intent_agent=IntentAgent(),
    )

    result = agent.classify("我的订单什么时候到？")

    assert result.intent == "order_query"


def test_hybrid_intent_agent_fallbacks_to_rule_when_llm_returns_none():
    agent = HybridIntentAgent(
        llm_intent_agent=FakeLLMIntentAgent(None),
        rule_intent_agent=IntentAgent(),
    )

    result = agent.classify("怎么退款？")

    assert result.intent == "knowledge_base_query"
