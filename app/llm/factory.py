import os

from dotenv import load_dotenv

from app.llm.base import BaseLLMClient
from app.llm.fake_client import FakeLLMClient
from app.llm.openai_compatible_client import OpenAICompatibleClient


def create_llm_client() -> BaseLLMClient:
    load_dotenv()

    enabled = os.getenv("LLM_ENABLED", "false").lower() == "true"
    if not enabled:
        return FakeLLMClient()

    return OpenAICompatibleClient()
