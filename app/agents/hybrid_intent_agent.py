from app.agents.intent_agent import IntentAgent
from app.agents.llm_intent_agent import LLMIntentAgent
from app.schemas.intent import IntentResult



class HybridIntentAgent:
    def __init__(
        self,
        llm_intent_agent: LLMIntentAgent,
        rule_intent_agent: IntentAgent,
        confidence_threshold: float = 0.7,
    ) -> None:
        self.llm_intent_agent = llm_intent_agent
        self.rule_intent_agent = rule_intent_agent
        self.confidence_threshold = confidence_threshold

    def classify(
        self,
        message: str,
        conversation_history: str = "",
    ) -> IntentResult:
        llm_result = self.llm_intent_agent.classify(
            message,
            conversation_history=conversation_history,
        )

        if llm_result and llm_result.confidence >= self.confidence_threshold:
            return llm_result

        return self.rule_intent_agent.classify(message)
