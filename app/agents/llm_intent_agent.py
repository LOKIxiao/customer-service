import json

from app.llm.base import BaseLLMClient
from app.schemas.intent import IntentResult


ALLOWED_INTENTS = {
    'order_query',
    'refund_policy',
    'ticket_create',
    'ticket_query',
    'memory_query',
    'human_handoff',
    'unknown',
}


class LLMIntentAgent:
    def __init__(self, llm_client: BaseLLMClient) -> None:
        self.llm_client = llm_client

    def classify(self, message: str) -> IntentResult | None:
        try:
            raw_result = self.llm_client.classify_intent(message)
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
