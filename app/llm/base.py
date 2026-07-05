from abc import ABC, abstractmethod


class BaseLLMClient(ABC):
    @abstractmethod
    def generate_customer_reply(
        self,
        user_message: str,
        intent: str,
        raw_reply: str,
    ) -> str:
        pass