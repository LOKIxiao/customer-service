from app.llm.base import BaseLLMClient


class FakeLLMClient(BaseLLMClient):
    def generate_customer_reply(
        self,
        user_message: str,
        intent: str,
        raw_reply: str,
    ) -> str:
        return raw_reply