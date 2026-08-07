from app.llm.base import BaseLLMClient


class ResponseAgent:
    def __init__(self, llm_client: BaseLLMClient) -> None:
        self.llm_client = llm_client

    def generate(
        self,
        user_message: str,
        intent: str,
        raw_reply: str,
        long_term_context: str = "",
        conversation_history: str = "",
    ) -> str:
        try:
            return self.llm_client.generate_customer_reply(
                user_message=user_message,
                intent=intent,
                raw_reply=raw_reply,
                long_term_context=long_term_context,
                conversation_history=conversation_history,
            )
        except Exception:
            return raw_reply
