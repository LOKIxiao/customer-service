from abc import ABC, abstractmethod


class BaseLLMClient(ABC):
    @abstractmethod
    def generate_customer_reply(
        self,
        user_message: str,
        intent: str,
        raw_reply: str,
        long_term_context: str = "",
    ) -> str:
        pass

    @abstractmethod
    def classify_intent(self, message: str) -> str:
        pass

    @abstractmethod
    def extract_user_facts(self, user_message: str, assistant_reply: str) -> str:
        pass