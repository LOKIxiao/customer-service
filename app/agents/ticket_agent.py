from typing import Any


class TicketAgent:
    def __init__(self, mcp_client: Any) -> None:
        self.mcp_client = mcp_client

    def handle(self, user_id: str, intent: str, message: str) -> str:
        if intent == "ticket_create":
            ticket = self.mcp_client.call_tool(
                "create_ticket",
                {"user_id": user_id, "content": message},
            )

            return (
                f"已为你创建工单 {ticket['ticket_id']}，"
                "当前状态是待处理，我们会尽快安排客服跟进。"
            )

        if intent == "ticket_query":
            result = self.mcp_client.call_tool("query_ticket", {"user_id": user_id})

            if not result["found"]:
                return "暂时没有查到你的工单记录。"

            ticket = result["ticket"]
            status_text = self._translate_status(ticket.get("status", "unknown"))

            return f"你的工单 {ticket['ticket_id']} 当前状态是{status_text}。"

        return "暂时无法处理该工单请求，请稍后转人工客服。"

    def _translate_status(self, status: str) -> str:
        status_map = {
            "pending": "待处理",
            "processing": "处理中",
            "resolved": "已解决",
            "closed": "已关闭",
        }

        return status_map.get(status, "未知状态")