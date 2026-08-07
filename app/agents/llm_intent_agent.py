import json

from app.llm.base import BaseLLMClient
from app.schemas.intent import IntentResult


ALLOWED_INTENTS = {
    'order_query',
    'knowledge_base_query',
    'ticket_create',
    'ticket_query',
    'memory_query',
    'human_handoff',
    'unknown',
}


class LLMIntentAgent:
    def __init__(self, llm_client: BaseLLMClient) -> None:
        self.llm_client = llm_client

    def classify(
        self,
        message: str,
        conversation_history: str = "",
    ) -> IntentResult | None:
        contextual_message = (
            f"【最近对话】\n{conversation_history}\n\n【当前用户消息】\n{message}"
            if conversation_history
            else message
        )
        try:
            raw_result = self.llm_client.classify_intent(contextual_message)
            data = json.loads(raw_result)

        except Exception:
            return None
        
        intent = data.get('intent', 'unknown')
        confidence = float(data.get('confidence', 0.0))
        slots = data.get("slots", {})
        need_clarification = bool(data.get("need_clarification", False))

        if intent not in ALLOWED_INTENTS:
            return None
        
        if not isinstance(slots, dict):
            slots = {}
        
        return IntentResult(
            intent=intent,
            confidence=confidence,
            slots=slots,
            need_clarification=need_clarification,
        )
