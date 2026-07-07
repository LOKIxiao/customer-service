from app.llm.base import BaseLLMClient


class FakeLLMClient(BaseLLMClient):
    def generate_customer_reply(
        self,
        user_message: str,
        intent: str,
        raw_reply: str,
    ) -> str:
        return raw_reply

    def classify_intent(self, message: str) -> str:
        return """
{
  "intent": "unknown",
  "confidence": 0.0,
  "slots": {},
  "need_clarification": true
}
""".strip()