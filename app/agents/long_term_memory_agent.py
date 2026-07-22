from typing import Any

from app.schemas.memory import ExtractedFact


class LongTermMemoryAgent:
    def __init__(self, mcp_client: Any) -> None:
        self.mcp_client = mcp_client

    def recall(self, user_id: str, query: str, top_k: int = 3) -> str:
        result = self.mcp_client.call_tool(
            "recall_user_memory",
            {"user_id": user_id, "query": query, "top_k": top_k},
        )
        memories = result["memories"]

        if not memories:
            return ""

        lines = "\n".join(f"- {memory['content']}" for memory in memories)
        return f"已知用户信息：\n{lines}"

    def remember(self, user_id: str, facts: list[ExtractedFact]) -> None:
        for fact in facts:
            self.mcp_client.call_tool(
                "save_user_memory",
                {"user_id": user_id, "category": fact.category, "content": fact.content},
            )
