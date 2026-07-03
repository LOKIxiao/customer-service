from pathlib import Path

from app.tools.ticket_tools import TICKETS_FILE, create_ticket, get_latest_ticket_by_user


class TicketAgent:
    def __init__(self, tickets_file: Path = TICKETS_FILE) -> None:
        self.tickets_file = tickets_file

    def handle(self, user_id: str, intent: str, message: str) -> str:
        if intent == "ticket_create":
            ticket = create_ticket(
                user_id=user_id,
                content=message,
                file_path=self.tickets_file,
            )

            return (
                f"已为你创建工单 {ticket['ticket_id']}，"
                "当前状态是待处理，我们会尽快安排客服跟进。"
            )

        if intent == "ticket_query":
            ticket = get_latest_ticket_by_user(
                user_id=user_id,
                file_path=self.tickets_file,
            )

            if ticket is None:
                return "暂时没有查到你的工单记录。"

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