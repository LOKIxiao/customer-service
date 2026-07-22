import json

from app.llm.base import BaseLLMClient
from app.schemas.memory import ALLOWED_MEMORY_CATEGORIES, ExtractedFact


class MemoryExtractionAgent:
    def __init__(self, llm_client: BaseLLMClient) -> None:
        self.llm_client = llm_client

    def extract(self, user_message: str, assistant_reply: str) -> list[ExtractedFact]:
        try:
            raw_result = self.llm_client.extract_user_facts(
                user_message=user_message,
                assistant_reply=assistant_reply,
            )
            data = json.loads(raw_result)
            facts = data.get("facts", [])
        except Exception:
            return []

        if not isinstance(facts, list):
            return []

        extracted: list[ExtractedFact] = []
        for fact in facts:
            if not isinstance(fact, dict):
                continue

            category = fact.get("category")
            content = fact.get("content")

            if category in ALLOWED_MEMORY_CATEGORIES and content:
                extracted.append(ExtractedFact(category=category, content=content))

        return extracted
