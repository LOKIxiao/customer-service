from typing import Any


class RAGAgent:
    def __init__(self, mcp_client: Any) -> None:
        self.mcp_client = mcp_client

    def handle(self, question: str) -> str:
        result = self.mcp_client.call_tool(
            "search_knowledge_base",
            {"query": question, "top_k": 3},
        )
        chunks = result["chunks"]

        if not chunks:
            return "我暂时没有在知识库中找到相关信息，请你换个问法试试。"

        context = "\n\n".join(
            f"来源：{chunk['source']}\n内容：{chunk['content']}"
            for chunk in chunks
        )

        return f"根据知识库内容：\n{context}"
