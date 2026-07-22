import hashlib
import os
from abc import ABC, abstractmethod

from dotenv import load_dotenv
from openai import OpenAI


class EmbeddingClient(ABC):
    @abstractmethod
    def embed(self, text: str) -> list[float]:
        pass

class FakeEmbeddingClient(EmbeddingClient):
    SEMANTIC_GROUPS = [
        ["退款", "退货", "退换", "售后", "原路", "多久到账", "多久", "工作日"],
        ["发票", "开票", "票据"],
        ["订单", "物流", "快递", "发货", "送达"],
        ["工单", "投诉", "反馈", "报修"],
        ["人工", "真人", "客服"],
        ["刚才", "之前", "问了什么", "历史"],
    ]

    def __init__(self, dimensions: int = 16) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions

        for group_index, keywords in enumerate(self.SEMANTIC_GROUPS):
            if group_index >= self.dimensions:
                break

            hit_count = sum(1 for keyword in keywords if keyword in text)
            if hit_count > 0:
                vector[group_index] += hit_count * 3.0

        for char in text:
            if char.isspace():
                continue

            index = int(hashlib.md5(char.encode("utf-8")).hexdigest(), 16) % self.dimensions
            vector[index] += 0.1

        return self._normalize(vector)
    
    def _normalize(self, vector: list[float]) -> list[float]:
        norm = sum(value * value for value in vector) ** 0.5
        if norm == 0:
            return vector

        return [value / norm for value in vector]


           

class QwenEmbeddingClient(EmbeddingClient):
    def __init__(self) -> None:
        load_dotenv()

        api_key = os.getenv("LLM_API_KEY")
        base_url = os.getenv(
            "EMBEDDING_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        model = os.getenv("EMBEDDING_MODEL", "text-embedding-v4")

        if not api_key:
            raise ValueError("LLM_API_KEY is required when using QwenEmbeddingClient")

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.model = model
    
    def embed(self, text: str) -> list[float]:
        response = self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding
